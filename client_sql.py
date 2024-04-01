import sqlite3
import json

_db_address = '/etc/x-ui/x-ui.db'
_db_address2 = 'example.db'
_max_allowed_connections = 1


class ClientSQL(object):
    def __init__(self):
        self.conn = sqlite3.connect(_db_address2)
        cursor = self.conn.cursor()
        cursor.execute(
            f'''CREATE TABLE IF NOT EXISTS client_limit (id TEXT PRIMARY KEY, limit_customer INTEGER DEFAULT {_max_allowed_connections});''')

        self.conn.commit()

    # Here you just create a simple and default tabel, then you can edit limit_customer for every client manually
    # or by running Upgrade script below. DEVELOPING
    def add_limit(self, uuid, limit=1):
        print(uuid)
        cursor = self.conn.cursor()
        cursor.execute(f'''INSERT OR IGNORE INTO client_limit VALUES ('{uuid}',{limit})''')
        self.conn.commit()




