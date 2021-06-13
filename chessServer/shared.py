import socket
from socket import socket as sock

PROGRAM_VERSION = 'V1.04'
NEW_GAME = '%MOVE -1000'
PLAY_BLACK = '%MOVE -1001'
PLAY_WHITE = '%MOVE -1002'

CONNECTED_WITH = ['connected with {} ({})', 'mit {} ({}) verbunden']
PROTOCOL_ERROR = ['Protocol Error', 'Protokollfehler']
INCORRECT_PW = ['Incorrect password', 'Falsches Passwort. Vielleicht wird der Name schon verwendet.']
WAIT_FOR_PLAYER = ['...waiting for player...', '...warte auf Spieler...']
ALREADY_ASSIGNED = ['\'{}\' is already assigned. Please choose a different name',
                    'Der Name \'{}\' ist schon vergeben. Waehle einen anderen Namen']
NOT_LINKED = ['You are not linked with any player.', 'Du bist mit keinem Spieler verbunden.']
TIMEOUT_ERROR = ['Error: connection timeout', 'Fehler: Zeitüberschreitung']
AUTH_ERROR = ['Authentication failed', 'Fehler bei der Authentifizierung']
TOO_MANY_IP = ['Too many users with same ip address', 'Zu viele Nutzer mit derselben IP-Adresse']

BUFFER_SIZE = 256
ETX = chr(0x03)  # ASCII 'end of text'
SEPARATOR_LF = '---------------------------------------\n'
SEPARATOR = '---------------------------------------'


class Language:
    EN = 0
    DE = 1
    __language = DE

    @staticmethod
    def set_en():
        Language.__language = Language.EN

    @staticmethod
    def set_de():
        Language.__language = Language.DE

    @staticmethod
    def set_lang(lang: int):
        Language.__language = lang % 2

    @staticmethod
    def get(item) -> str:
        if isinstance(item, list):
            return item[Language.__language]
        else:
            return str(item)


def string(item) -> str:
    return Language.get(item)


def get_local_ip():
    s = sock(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(('8.8.8.8', 80))
    ip = s.getsockname()[0]
    s.close()
    return ip


def elo_rating(rating_a: int, rating_b: int, result: float, weight: int) -> int:
    expectancy = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    return round(rating_a + weight * (result - expectancy))
