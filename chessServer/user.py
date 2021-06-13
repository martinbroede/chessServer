import typing
from datetime import datetime
from socket import timeout
from threading import Thread
from typing import List

from chessServer.shared import *

T_Socket = typing.Union[sock, None]


class User:
    _id: int = 1

    def __init__(self, user_socket: T_Socket, ip: str):
        self.played_games = 0
        self.scoring_zero = 0  # number of games lost
        self.scoring_half = 0  # number of drawn games
        self.scoring_one = 0  # number of games won
        self.rating = 1000
        self.socket: T_Socket = user_socket
        self.ip: str = ip
        self.last_login: str = datetime.now().strftime('%Y.%m.%d.%H:%M:%S')
        self.__elo_weight = 40
        self.__ID = User._id
        self.__NAME = ''
        self.__password = ''
        self.__data = ''
        self.messages: List[str] = list()
        User._id += 1

    def __eq__(self, other):
        return self.__ID == other.get_id()

    def __hash__(self):
        return self.__ID

    def __str__(self):
        return 'ID_{} {} L:{}/D:{}/W:{}/#T:{} ELO:{}({})'.format(
            self.__ID,
            self.__NAME,
            self.scoring_zero,
            self.scoring_half,
            self.scoring_one,
            self.played_games,
            self.rating,
            self.__elo_weight
        )

    @staticmethod
    def create_user(attr: tuple):
        user = User(None, '')
        # ID, IP, NAME, PW, GAMES, ZERO, HALF, ONE, RATING, WEIGHT, LASTLOGIN from USERS :
        [user.__ID, user.ip, user.__NAME, user.__password,
         user.played_games, user.scoring_zero, user.scoring_half, user.scoring_one,
         user.rating, user.__elo_weight, user.last_login] = attr
        return user

    @staticmethod
    def set_id(_id: int) -> None:
        User._id = _id

    def __recv(self) -> str:
        return self.socket.recv(BUFFER_SIZE).decode()

    def renew_connection(self, skt: sock, ip: str, date: str) -> None:
        self.socket = skt
        self.ip = ip
        self.last_login = date

    def set_name(self, name: str) -> None:
        if not self.__NAME:
            self.__NAME = name
        else:
            print('user name can not be changed')

    def set_password(self, pw: str) -> None:
        if not self.__password:
            self.__password = pw
        elif self.__password == '%RESET_PASSWORD':
            self.__password = pw
            print(f'{self.__NAME} password reset')
        else:
            print('user password can not be changed')

    def reset_password(self) -> None:
        self.__password = '%RESET_PASSWORD'

    def set_timeout(self, time_out: float) -> None:
        self.socket.settimeout(time_out)

    def get_elo_weight(self) -> int:
        return self.__elo_weight

    def get_name(self) -> str:
        return self.__NAME

    def get_id(self) -> int:
        return self.__ID

    def get_password(self) -> str:
        return self.__password

    def dec_elo_weight(self) -> None:
        if self.__elo_weight > 11:
            self.__elo_weight -= 2

    def notify(self, msg: str) -> None:
        self.socket.send((msg + ETX).encode('utf-8'))

    def receive_message(self) -> str:
        msg = self.next_message()
        if msg:
            self.messages.append(msg)
        return msg

    def next_message(self) -> str:
        msg = self.__next_message()
        if not msg:
            self.__data += self.__recv()
            return self.__next_message()
        return msg

    def __next_message(self) -> str:
        count = self.__data.count(ETX)
        if count == 0:
            return ''
        split = self.__data.split(ETX, maxsplit=1)
        if len(split) == 2:
            self.__data = split[1]
            return split[0]
        elif len(split) == 1:
            self.__data = ''
            return split[0]

    def error(self, message: str) -> None:
        self.socket.settimeout(1)
        th = Thread(target=self.__error, args=(message,), name='id_' + str(self.__ID) + '_error')
        th.start()

    def __error(self, message: str) -> None:
        try:
            self.notify('%INFO ' + message)
            self.notify('%ECHO?')
            print(self.__recv())
        except timeout:
            pass
        except ConnectionError:
            pass
        except Exception as ex:
            print(str(ex))
        self.socket.close()
        print(message + '\n' + 'socket id_' + str(self.__ID) + ' closed')
