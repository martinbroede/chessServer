import logging
import sqlite3

from chessServer.user import User


class Database:  # simple wrapper class for sqlite3
    def __init__(self, filename: str):
        try:
            self.conn = sqlite3.connect(filename)
            logging.info('opened database ' + filename)
            self.conn.execute('''CREATE TABLE USERS
                                (ID INT PRIMARY KEY NOT NULL,
                                IP TEXT,
                                NAME TEXT NOT NULL,
                                PW TEXT NOT NULL,
                                GAMES INT NOT NULL,
                                ZERO INT NOT NULL,
                                HALF INT NOT NULL,
                                ONE INT NOT NULL,
                                RATING INT NOT NULL,
                                WEIGHT INT NOT NULL,
                                LASTLOGIN TEXT
                                )''')
            logging.info('table created')
        except sqlite3.OperationalError as ex:
            logging.info(str(ex))

    def close(self):
        self.conn.close()

    def clear(self):
        self.conn.execute('DELETE FROM USERS')

    def save(self):
        self.conn.commit()
        self.conn.close()

    def get_users(self) -> tuple:
        users = set()
        max_id = 0
        sql_cmd = 'SELECT ID, IP, NAME, PW, GAMES, ZERO, HALF, ONE, RATING, WEIGHT, LASTLOGIN from USERS'
        cursor = self.conn.execute(sql_cmd)
        for attributes in cursor:
            max_id = max(max_id, attributes[0])
            users.add(User.create_user(attributes))
        return users, max_id

    def insert(self, users: set) -> None:
        for user in users:
            self._insert(user)

    def _insert(self, user: User):
        def t(x):  # sql TEXT
            return '\"' + str(x) + '\"'

        try:
            sql_cmd = f'''INSERT INTO USERS (ID, IP, NAME, PW, GAMES, ZERO, HALF, ONE, RATING, WEIGHT, LASTLOGIN) VALUES(
                {user.get_id()},{t(user.ip)},{t(user.get_name())},{t(user.get_password())},
                {user.played_games},{user.scoring_zero},{user.scoring_half},{user.scoring_one},
                {user.rating},{user.get_elo_weight()},{t(user.last_login)})'''
            self.conn.execute(sql_cmd)
        except Exception as ex:
            logging.info(str(ex))
