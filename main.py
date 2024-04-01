import os
import sqlite3
import time
import requests
import threading
import schedule
import json
import copy
import collections
from client_sql import _db_address, _db_address2, ClientSQL, _max_allowed_connections

_user_last_id = 0
_telegrambot_token = ''
_telegram_chat_id = ''  # you can get this in @cid_bot bot.
port_client_connections = collections.defaultdict(dict)


def getUsers():
    global _user_last_id
    conn = sqlite3.connect(_db_address)
    sql = ClientSQL()
    cursor = conn.execute(f"select id,remark,port,settings from inbounds where id > {_user_last_id}")
    users_list = []
    for c in cursor:
        clients_id = []
        cleaned_json_string = c[3].replace('\n', '').replace(' ', '')
        cleaned_json_string = dict(json.loads(cleaned_json_string))
        clients = cleaned_json_string.get("clients")

        for client in clients:
            uuid = client.get("id")
            if uuid:
                clients_id.append(uuid)
                sql.add_limit(uuid, _max_allowed_connections)
        # Remove newlines and spaces

        # Print the cleaned string
        print(cleaned_json_string)
        users_list.append({'name': c[1], 'port': c[2], "uuid": clients_id})
        _user_last_id = c[0]
    conn.close()
    return users_list


def disableAccount(user_port, uuid):
    conn = sqlite3.connect(_db_address)
    cursor = conn.execute(f"select settings from inbounds where port = {user_port}")
    setting = cursor.fetchone()[0]
    cleaned_json_string = setting.replace('\n', '').replace(' ', '')

    cleaned_json_dict = json.loads(cleaned_json_string)
    clients = copy.deepcopy(cleaned_json_dict.get("clients"))
    for client in clients:
        if client['id'] == uuid:
            client['enable'] = False

    cleaned_json_dict['clients'] = clients
    cleaned_json_string = json.dumps(cleaned_json_dict)
    # Update the database using parameterized query
    conn.execute("UPDATE inbounds SET settings = ? WHERE port = ?", (cleaned_json_string, user_port))
    conn.commit()  # Commit the transaction

    conn.close()
    time.sleep(2)
    os.popen("x-ui restart")
    time.sleep(3)


def enableAccount(user_port, uuid):
    conn = sqlite3.connect(_db_address)
    cursor = conn.execute(f"select settings from inbounds where port = {user_port}")
    setting = cursor.fetchone()[0]
    cleaned_json_string = setting.replace('\n', '').replace(' ', '')

    cleaned_json_dict = json.loads(cleaned_json_string)
    clients = copy.deepcopy(cleaned_json_dict.get("clients"))
    for client in clients:
        if client['id'] == uuid:
            client['enable'] = True

    cleaned_json_dict['clients'] = clients
    cleaned_json_string = json.dumps(cleaned_json_dict)
    # Update the database using parameterized query
    conn.execute("UPDATE inbounds SET settings = ? WHERE port = ?", (cleaned_json_string, user_port))
    conn.commit()  # Commit the transaction

    conn.close()
    time.sleep(2)
    os.popen("x-ui restart")
    time.sleep(3)


def checkNewUsers():
    conn = sqlite3.connect(_db_address)
    cursor = conn.execute(f"select count(*) from inbounds WHERE id > {_user_last_id}")
    new_counts = cursor.fetchone()[0]
    conn.close()
    if new_counts > 0:
        init()


def init():
    users_list = getUsers()
    for user in users_list:
        thread = AccessChecker(user)
        thread.start()
        print("starting checker for : " + user['name'])


class AccessChecker(threading.Thread):
    def __init__(self, user):
        threading.Thread.__init__(self)
        self.user = user

    def run(self):
        # global _max_allowed_connections  <<if you get variable error uncomment this.
        user_remark = self.user['name']
        user_port = self.user['port']
        user_uuid_total = self.user['uuid']  # Assuming there's a UUID associated with each user

        while True:
            for user_uuid in user_uuid_total:
                conn = sqlite3.connect(_db_address2)
                cursor = conn.execute(f"select limit_customer from client_limit where id = ?", (user_uuid,))
                _max_allowed_connections = cursor.fetchone()[0]

                netstate_data = os.popen("netstat -np 2>/dev/null | grep :" + str(
                    user_port) + " | awk '{if($3!=0) print $5 }' | cut -d: -f1 | sort | uniq -c | sort -nr | head").read()

                netstate_data = str(netstate_data)
                connection_count = len(netstate_data.split("\n")) - 1

                # Update the number of connections for the client and port
                port_client_connections[user_port][user_uuid] = connection_count

                if connection_count > _max_allowed_connections:
                    user_remark = user_remark.replace(" ", "%20")
                    requests.get(
                        f'https://api.telegram.org/bot{_telegrambot_token}/sendMessage?chat_id={_telegram_chat_id}&text={user_remark}%20locked')
                    disableAccount(user_port=user_port, uuid=user_uuid)
                    print(f"inbound with port {user_port} blocked")
                else:
                    # we should consider another limitation too, like time and traffic. Not finished yet
                    enableAccount(user_port=user_port, uuid=user_uuid)

                    time.sleep(2)
            print(port_client_connections)


def sendDatabaseToTelegram():
    with open(_db_address, 'rb') as file:
        requests.post(
            f'https://api.telegram.org/bot{_telegrambot_token}/sendDocument',
            data={'chat_id': _telegram_chat_id},
            files={'document': file}
        )


# Send the database to Telegram at the start
sendDatabaseToTelegram()

init()
schedule.every(10).minutes.do(checkNewUsers)
while True:
    schedule.run_pending()
    time.sleep(1)
