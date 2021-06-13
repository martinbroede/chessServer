import logging
import traceback
from socket import socket as sock
from socket import timeout
from threading import Thread

from chessServer.shared import BUFFER_SIZE, ETX


class Client:
    def __init__(self, hostname: str, port, authentication: str, name: str, password: str, terminal_mode: bool = True):
        self.hostname = hostname
        self.port = int(port)
        self.authentication = authentication
        self.socket = sock()
        self.name = name
        self.__data = str()

        try:
            self.socket.connect((hostname, self.port))
        except ConnectionRefusedError:
            print('CONNECTION REFUSED')
            return
        logging.info('connected')

        self.send(authentication)

        if name != 'admin':
            try:
                self.send('%NAME ' + self.name)
                self.send(password)
            except ConnectionError:
                self.socket.close()
                logging.info('CONNECTION ERROR')
                return
            except OSError:
                self.socket.close()
                logging.info('OS ERROR')
                traceback.print_exc()
                return
        else:
            try:
                self.send('get')
            except ConnectionError:
                self.socket.close()
                logging.info('CONNECTION ERROR')
                return
            except OSError as ex:
                self.socket.close()
                logging.info('OS ERROR')
                logging.error(str(ex))
                return

        if terminal_mode:
            self.sender = Thread(target=self.__sender, name=self.name + ' sender')
            self.receiver = Thread(target=self.__receiver, name=self.name + ' receiver')
            self.sender.daemon = True
            self.sender.start()
            self.receiver.start()

    def send(self, text: str):
        self.socket.send((text + ETX).encode('utf-8'))

    def next_message(self) -> str:
        msg = self.__next_message()
        if not msg:
            self.__data += self._recv()
            msg = self.__next_message()
            if self.__data and not msg:
                return '%INCOMPLETE'
            else:
                return msg
        return msg

    def __next_message(self) -> str:
        count = self.__data.count(ETX)
        if count == 0:
            return ''
        split = self.__data.split(ETX, 1)
        if len(split) == 2:
            self.__data = split[1]
            return split[0]
        elif len(split) == 1:
            self.__data = ''
            return split[0]

    def __sender(self):
        while True:
            try:
                text = input()
                if text == '%QUIT':
                    self.socket.close()
                    logging.info('closed socket')
                    break
                self.send(text)
                print(self.name + ':' + text)

            except ConnectionError:
                self.socket.close()
                logging.info('CONNECTION ERROR')
                return
            except OSError as ex:
                self.socket.close()
                logging.info('OS ERROR')
                logging.info(str(ex))
                return

    def _recv(self) -> str:
        return self.socket.recv(BUFFER_SIZE).decode()

    def __receiver(self):
        while True:
            try:
                msg = self.next_message()
                if not msg:
                    logging.info('nothing to receive')
                    self.socket.close()
                    return
                elif msg != '%INCOMPLETE':
                    print(msg)
            except timeout:
                pass
            except ConnectionError:
                logging.info('CONNECTION ERROR (RECEIVER)')
                break
            except OSError as ex:
                self.socket.close()
                logging.info('OS ERROR (RECEIVER)')
                logging.error(str(ex))
                break
