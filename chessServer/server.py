import logging
import os
import sqlite3
import threading
import time
import traceback
import typing
from datetime import datetime
from pathlib import Path
from random import randint
from socket import timeout
from threading import Thread
from typing import Dict, Set

from chessServer import Database
from chessServer.shared import *
from chessServer.user import User

T_User = typing.Union[User, None]
T_Socket = typing.Union[sock, None]
T_Port = typing.Union[str, int]


class Server:
    MAX_ATTEMPTS = 5
    TIMEOUT = 5
    BACKLOG = 10
    MAX_PER_IP = 25
    LINK_INTERVAL = 10
    DB_UPDATE_INTERVAL = 3600

    # all time specifications in seconds

    def __init__(self, hostname: str, port: T_Port, authentication: str, admin_authentication: str):
        self.HOSTNAME = hostname
        self.SOCKET_NAME: str = str()
        self.__port: int = int(port)
        self.__authentication = authentication
        self.__admin_authentication = admin_authentication
        self.__server_socket = sock()
        self._admin = None
        self._last_game: str = str()
        self._ip_addresses: Dict[str, int] = dict()
        self._all_users: Set[User] = set()
        self._online_users: Set[User] = set()
        self._users_to_link: Set[User] = set()
        self._unlinked_users: Set[User] = set()
        self._user_wait_loop: Set[User] = set()
        self._disconnected_users: Set[User] = set()
        self._linked_users: Dict[User, User] = dict()
        self._lock = threading.Lock()
        self._stop = False

        abs_path = Path('.').absolute()
        sub_dir_name = f'data_{hostname}_{port}'.replace('.', '_')
        self.DATA_DIR = f'{abs_path}/{sub_dir_name}'
        self.DATABASE_FILENAME = f'{self.DATA_DIR}/users.db'
        try:
            os.mkdir(self.DATA_DIR)
            logging.info(f'directory {sub_dir_name} created')
        except FileExistsError:
            logging.info(f'directory {sub_dir_name} already exists')

    def get_port(self) -> int:
        return self.__port

    def run(self):
        # try to bind one of the ports from (port) to (port + max_attempts - 1):
        for attempt in range(Server.MAX_ATTEMPTS):
            try:
                self.__server_socket.bind((self.HOSTNAME, self.__port))
                break
            except OSError:
                logging.info(f'binding {self.HOSTNAME}:{self.__port} failed')
                self.__port += 1
                if attempt != Server.MAX_ATTEMPTS - 1:
                    continue
                else:
                    logging.info('binding not possible')
                    return

        self.SOCKET_NAME = str(self.__server_socket.getsockname())
        logging.info(f'binding {self.SOCKET_NAME} successful')

        main_loop = Thread(target=self.__main_loop, name=f'{self.SOCKET_NAME} main loop')
        main_loop.start()
        administrator = Thread(target=self.__administrate, name=f'{self.SOCKET_NAME} administrator')
        administrator.daemon = True
        administrator.start()
        request_manager = Thread(target=self.__manage_user_requests, name=f'{self.SOCKET_NAME}  request manager')
        request_manager.start()

    def register_user(self, user: User) -> None:
        self.__add_ip(user.ip)
        self._user_wait_loop.add(user)
        self._all_users.add(user)

    def sign_off(self, user: User) -> None:
        self._online_users.remove(user)
        self.__set_user_offline(user)
        user.socket.close()
        logging.info(f'signed off {user.get_name()}')

    def remove_user(self, user: User) -> None:
        if user in self._online_users:
            self.sign_off(user)
        self._all_users.remove(user)

    def stop(self) -> None:
        self._stop = True

    def execute(self, command: str) -> str:

        def remove_user(args: list) -> str:
            if len(args) > 0:
                user = self._get_user_by_name(args[0])
                if not user:
                    return f'no user named {args[0]}'
                self.remove_user(user)
                return f'removed user {args[0]}'
            return 'too few arguments'

        def notify_user(args: list) -> str:
            if len(args) < 2:
                return 'too few arguments - notify *name* *message*'
            else:
                user = self._get_online_user_by_name(args[0])
                if user:
                    user.notify(args[1])
                    return '{} notified'.format(user.get_name())
                else:
                    return f'no user online named{args[0]}'

        def notify_all(args: list) -> str:
            if len(args) < 2:
                return 'too few arguments - notify_all users *message*'  # todo ...
            else:
                for user in self._online_users:
                    try:
                        user.notify(args[1])
                        logging.debug('{} notified'.format(user.get_name()))
                    except ConnectionError as ex:
                        logging.info(str(ex))
                        self._disconnected_users.add(user)
                        continue
                    except Exception as ex:
                        logging.error(str(ex))
                        continue
                return 'notified users'

        def sign_off_user(args: list) -> str:
            if len(args) == 0:
                return 'too few arguments - remove *name*'
            name = args[0]
            try:
                user_to_del = self._get_online_user_by_name(name)
                self.sign_off(user_to_del)
                return 'signed off ' + name
            except ValueError as ex:
                return str(ex)

        def set_language(args: list) -> str:
            lang = ['English', 'German']
            Language.set_lang(int(args[0]))
            return 'set language to ' + lang[int(args[0])]

        def reset_password(args: list) -> str:
            if len(args) < 1:
                return 'too few arguments - resetpw *username*'
            else:
                user = self._get_user_by_name(args[0])
                if user:
                    user.reset_password()
                    return '{} password reset'.format(user.get_name())
                else:
                    return 'no user named {}'.format(args[0])

        def fetch_feedback(_) -> str:
            feedback = list()
            for file_name in os.listdir(self.DATA_DIR):
                if file_name.endswith('.txt'):
                    try:
                        with open(f'{self.DATA_DIR}/{file_name}', 'r') as file:
                            feedback.append(file.read())
                    except Exception as ex:
                        logging.error(str(ex))
            return f'\n{SEPARATOR}\n'.join(feedback)

        def get_info(_) -> str:
            return f'active threads: {str(threading.activeCount())}\n' \
                   f'users: {len(self._all_users)}\n' \
                   f'online: {len(self._online_users)}\n' \
                   f'linked users: {len(self._linked_users)}'

        def update_db(_) -> str:
            try:
                db = Database(self.DATABASE_FILENAME)
                db.clear()
                db.insert(self._all_users)
                db.save()
                return 'database updated'
            except sqlite3.OperationalError:
                return 'update database not possible. most likely db is locked'
            except Exception as ex:
                return str("ERROR DB UPDATE - " + str(ex))

        def get_rating_chart(_) -> str:
            out = list()
            users = list(self._all_users)
            users.sort(key=lambda c: c.rating, reverse=True)
            n = 0
            for user in users:
                if user in self._online_users:
                    online_marker = '(*)'
                else:
                    online_marker = '(o)'
                if user.played_games > 0:
                    out.append(f'{n + 1}. {online_marker} {user.get_name()} - {user.rating}')
                    n += 1
                if n >= 10:
                    break
            out.append(SEPARATOR)
            if self._last_game:
                out.append(self._last_game)
                out.append(SEPARATOR)
            out.append(
                f'online: {len(self._online_users)} / offline: {len(self._all_users) - len(self._online_users)}')
            out.append('online: (*) / offline: (o)')
            return '\n'.join(out)

        def get_users(_) -> str:
            out = list()
            if self._online_users:
                out.append('online:')
                for user in self._online_users:
                    out.append(str(user))
                out.append(f'#online:{str(len(self._online_users))}')
            else:
                out.append('no users online')
            out.append(SEPARATOR)
            offline_users = self._all_users - self._online_users
            if offline_users:
                out.append('offline:')
                for user in offline_users:
                    out.append(str(user))
                out.append('#offline:' + str(len(offline_users)))
            else:
                out.append('no users offline')
            return '\n'.join(out)

        def get_threads(_) -> str:
            out = list()
            out.append('threads:')
            for thread in threading.enumerate():
                out.append(thread.getName())
            return '\n'.join(out)

        def get_ip_addresses(_) -> str:
            out = list()
            user_count = 0
            for item in self._ip_addresses.items():
                user_count += item[1]
                out.append(str(item))
            out.append('TOTAL: ' + str(user_count))
            return '\n'.join(out)

        def get_links(_) -> str:
            out = list()
            for user_item in self._linked_users.items():
                out.append(str(user_item[0]) + ' <-> ' + str(user_item[1]))
            self._unlinked_users.clear()
            self._unlinked_users.update(self._online_users - set(self._linked_users))
            if self._unlinked_users:
                out.append('unlinked:')
                for user in self._unlinked_users:
                    out.append(str(user))
            out.append('linked: {} / unlinked: {}'.format(len(self._linked_users), len(self._unlinked_users)))
            return '\n'.join(out)

        def stop(_) -> str:
            self.stop()
            return f'stop server script in {str(Server.TIMEOUT)}  seconds'

        def shutdown(_) -> str:
            os.system('shutdown -h 0')
            return 'shut server down immediately'

        commands = {
            'feedback': fetch_feedback,
            'get': get_users,
            'info': get_info,
            'ip': get_ip_addresses,
            'links': get_links,
            'list': get_threads,
            'notify': notify_user,
            'notify_all': notify_all,
            'rating': get_rating_chart,
            'resetpw': reset_password,
            'remove': remove_user,
            'setlang': set_language,
            'signoff': sign_off_user,
            'stop': stop,
            'shutdown': shutdown,
            'update': update_db
        }

        arguments = command.split(maxsplit=2)
        if not arguments:
            return 'no arguments'
        command = arguments[0]
        if command in commands:
            return SEPARATOR_LF + commands.get(command)(arguments[1:]) + '\n' + SEPARATOR_LF
        else:
            notification = f'command \'{command}\' not found.\nvalid commands:\n#####\n'
            for command in commands:
                notification += command + '\n'
            return f'{SEPARATOR_LF}{notification}#####\n{SEPARATOR_LF}'

    def _get_user_by_name(self, name: str) -> T_User:
        for user in self._all_users:
            if name == user.get_name():
                return user
        return None

    def _get_online_user_by_name(self, name: str) -> T_User:
        for user in self._online_users:
            if user.get_name() == name:
                return user
        return None

    def __manage_user_requests(self):
        self.__server_socket.settimeout(Server.TIMEOUT)
        self.__server_socket.listen(Server.BACKLOG)
        last_db_update = time.time()

        while not self._stop:

            if time.time() - last_db_update > Server.DB_UPDATE_INTERVAL:
                logging.info(self.execute('update'))  # database update
                last_db_update = time.time()

            logging.debug('listening...')
            try:
                skt, _address = self.__server_socket.accept()
            except timeout:
                logging.debug('server socket timeout')
                continue

            ip = _address[0]
            address = str(_address)
            logging.info(f'connected to {str(address)}')

            new_user = User(skt, ip)
            new_user.set_timeout(0.9)
            try:
                authentication = new_user.next_message()

                if authentication == self.__admin_authentication:
                    if self._admin:
                        self._admin.notify('ERROR: ADMIN SIGNED IN TWICE')
                        self._admin.socket.close()
                    self._admin = new_user
                    self._admin.set_name('admin')
                    self._admin.set_timeout(0)
                    self._admin.notify(f'database:\n{self.DATABASE_FILENAME}\nprogram version:{PROGRAM_VERSION}')
                    logging.info('admin connected')
                    continue

                if not authentication == self.__authentication:
                    new_user.error(string(AUTH_ERROR))
                    continue

                user_name = new_user.next_message()
                if not user_name.startswith('%NAME '):
                    new_user.error(string(PROTOCOL_ERROR))
                    continue
                else:
                    try:
                        user_name = user_name.split(maxsplit=1)[1]
                    except IndexError:
                        new_user.error(string(PROTOCOL_ERROR))
                        continue

                known_user: T_User = self._get_user_by_name(user_name)

                if known_user:

                    if known_user in self._online_users:
                        new_user.error(string(ALREADY_ASSIGNED).format(user_name))
                        continue

                    user_password = new_user.next_message()
                    if known_user.get_password() == '%RESET_PASSWORD':
                        known_user.set_password(user_password)
                    elif user_password != known_user.get_password():
                        new_user.error(string(INCORRECT_PW))
                        continue

                    known_user.renew_connection(skt, ip, datetime.now().strftime('%Y.%m.%d.%H:%M:%S'))
                    new_user = known_user

                else:
                    user_password = new_user.next_message()
                    new_user.set_password(user_password)
                    new_user.set_name(user_name)

                new_user.notify('WELCOME ' + user_name)

            except timeout:
                try:
                    new_user.error(string(TIMEOUT_ERROR))
                except OSError:
                    pass
                logging.info('TIMEOUT ERROR (ADMITTANCE)')
                continue
            except ConnectionError:
                logging.info('CONNECTION ERROR (ADMITTANCE)')
                skt.close()
                continue
            except OSError as ex:
                logging.error('OS ERROR (ADMITTANCE)')
                logging.error(str(ex))
                skt.close()
                continue
            except Exception as ex:
                logging.error(str(ex))
                skt.close()
                continue

            logging.info(f'{user_name} has connected')

            if Server.MAX_PER_IP <= self._ip_addresses.setdefault(new_user.ip, 0):
                new_user.error(string(TOO_MANY_IP))
                continue

            self._lock.acquire(True)
            self.register_user(new_user)
            new_user.set_timeout(0)
            self._lock.release()

        logging.info(f'{self.SOCKET_NAME} request manager interrupted')

    def __administrate(self):
        while not self._stop:
            command = input()
            print(self.execute(command))
        logging.info(f'{self.SOCKET_NAME} administrator interrupted')

    def __add_ip(self, ip):
        # is called in a locked context
        if ip in self._ip_addresses:
            self._ip_addresses[ip] += 1
        else:
            self._ip_addresses.update({ip: 1})

    def __discard_ip(self, ip):
        self._lock.acquire(True)  # block
        if ip in self._ip_addresses:
            self._ip_addresses[ip] -= 1
        else:
            # will not happen...
            logging.error('mismatch: {} not stored in ip_addresses'.format(ip))
            self._lock.release()
            return
        if self._ip_addresses[ip] == 0:
            self._ip_addresses.pop(ip)
        self._lock.release()

    def __remove_disconnected_users(self):
        self._online_users.difference_update(self._disconnected_users)
        for user in self._disconnected_users:
            self.__set_user_offline(user)
        self._disconnected_users.clear()

    def __set_user_offline(self, user: User):
        self.__discard_ip(user.ip)
        logging.info(f'{user.get_name()} left')
        if user in self._users_to_link:
            self._users_to_link.remove(user)
        if user in self._linked_users:
            self._linked_users.pop(self._linked_users[user])
            self._linked_users.pop(user)

    def __add_users(self):
        # the user_wait_loop makes sure the request manager thread can add users while other threads run
        if self._lock.acquire(False):  # non blocking
            self._online_users.update(self._user_wait_loop)
            self._user_wait_loop.clear()
            self._lock.release()
        else:
            logging.info('thread is locked - did not add users')

    def __process_messages(self) -> None:
        user_a: User
        originator: User
        for originator in self._online_users:
            if originator.messages:
                msg = originator.messages.pop(0)
                logging.debug(f'{originator.get_name()}:{msg}')
            else:
                continue

            if msg.startswith('%SERVER'):
                user_a = originator

                def link():
                    if user_a not in self._linked_users:
                        self._users_to_link.add(user_a)
                        user_a.notify('%NOTE {}'.format(string(WAIT_FOR_PLAYER)))

                def link_to(username: str):
                    user_b: T_User = self._get_online_user_by_name(username)
                    if user_b and user_b not in self._linked_users:
                        self.__link_users(user_a, user_b)

                def feedback(text: str):
                    date = datetime.now().strftime('d%m-%dt%H-%M-%S')
                    file_name = 'feedback-{}-{}.txt'.format(date, user_a.get_name())
                    full_path_name = f'{self.DATA_DIR}/{file_name}'
                    f = open(full_path_name, 'w')
                    f.write(text)
                    f.close()

                def get_elo_rating():
                    output = '%ELO [ {} - {} ]\n'.format(user_a.get_name(), user_a.rating)
                    output += self.execute('rating')
                    user_a.notify(output)

                def disconnect():
                    self._disconnected_users.add(user_a)

                def update_rating(scoring: str):
                    user_b: User
                    scoring = float(scoring)
                    if user_a in self._linked_users:
                        user_b = self._linked_users.get(user_a)
                        a = user_a.rating
                        b = user_b.rating
                        elo_weight = min(user_a.get_elo_weight(), user_b.get_elo_weight())
                        a_rating = elo_rating(a, b, scoring, elo_weight)
                        b_rating = elo_rating(b, a, 1.0 - scoring, elo_weight)
                        logging.info('update rating:\n{}: {} -> {}\n{}: {} -> {}'.format(
                            user_a.get_name(),
                            a, a_rating,
                            user_b.get_name(),
                            b, b_rating
                        ))
                        user_a.rating = a_rating
                        user_b.rating = b_rating
                        user_a.dec_elo_weight()
                        user_b.dec_elo_weight()
                        self._linked_users.pop(user_a)
                        self._linked_users.pop(user_b)
                        user_a.played_games += 1
                        user_b.played_games += 1
                        if scoring == 0.0:
                            user_a.scoring_zero += 1
                            user_b.scoring_one += 1
                        elif scoring == 1.0:
                            user_a.scoring_one += 1
                            user_b.scoring_zero += 1
                        else:
                            user_a.scoring_half += 1
                            user_b.scoring_half += 1

                        date = datetime.now().strftime('%d.%m.')
                        if scoring == 1.0:
                            self._last_game = f'{user_a.get_name()} - {user_b.get_name()} 1:0 ({date})'
                        elif scoring == 0.0:
                            self._last_game = f'{user_a.get_name()} - {user_b.get_name()} 0:1 ({date})'
                        elif scoring == 0.5:
                            self._last_game = f'{user_a.get_name()} - {user_b.get_name()} 1/2:1/2 ({date})'

                commands = {
                    'LINK': link,
                    'LINKTO': link_to,
                    'FEEDBACK': feedback,
                    'ELO': get_elo_rating,
                    'SCORING': update_rating,
                    'DISCONNECT': disconnect,
                }

                arguments = msg.split(maxsplit=2)
                if not arguments:
                    logging.info(f'{msg} - no arguments')
                else:
                    try:
                        command = arguments[1]
                        if command in commands:
                            if len(arguments) == 3:
                                commands.get(command)(arguments[2])
                            elif len(arguments) == 2:
                                commands.get(command)()

                    except IndexError:
                        logging.info('index error')

            else:
                recipient = None
                if originator in self._linked_users:
                    recipient = self._linked_users[originator]

                if recipient:
                    try:
                        recipient.notify(msg)
                    except ConnectionError:
                        logging.info('CONNECTION ERROR (NOTIFY ' + recipient.get_name() + ')')
                        self._disconnected_users.add(recipient)
                        continue
                    except OSError:
                        logging.info('OS ERROR (NOTIFY ' + recipient.get_name() + ')')
                        traceback.print_exc()
                        self._disconnected_users.add(recipient)
                        continue
                    except Exception as ex:
                        logging.error(str(ex))
                else:
                    try:
                        originator.notify('%NOTE ' + string(NOT_LINKED))
                    except ConnectionError:
                        logging.info('CONNECTION ERROR (NOTIFY ' + originator.get_name() + ')')
                        self._disconnected_users.add(originator)
                        continue
                    except OSError as ex:
                        logging.error('OS ERROR (NOTIFY ' + originator.get_name() + ')')
                        logging.error(str(ex))
                        self._disconnected_users.add(originator)
                        continue
                    except Exception as ex:
                        logging.error(str(ex))

        if self._admin:
            if self._admin.messages:
                cmd = self._admin.messages.pop(0)
                try:
                    result = self.execute(cmd)
                    self._admin.notify(result)
                except ConnectionError:
                    logging.info('CONNECTION ERROR (NOTIFY ADMIN)')
                    self._admin.get_socket.close()
                    self._admin = None
                except OSError as ex:
                    logging.error('OS ERROR (NOTIFY ADMIN)')
                    logging.error(str(ex))
                    self._admin.get_socket.close()
                    self._admin = None

    def __link_users(self, user_a: User, user_b: User) -> None:
        new_link = {user_a: user_b,
                    user_b: user_a}
        user_a.notify('%NAME ' + user_b.get_name())
        user_a.notify('%NOTE ' + string(CONNECTED_WITH).format(user_b.get_name(), user_b.rating))
        user_b.notify('%NAME ' + user_a.get_name())
        user_b.notify('%NOTE ' + string(CONNECTED_WITH).format(user_a.get_name(), user_a.rating))
        try:
            self._users_to_link.remove(user_a)
        except KeyError:
            logging.debug(f'user {user_a.get_name()} not in _users_to_link')
        try:
            self._users_to_link.remove(user_b)
        except KeyError:
            logging.debug(f'user {user_b.get_name()} not in _users_to_link')
        self._linked_users.update(new_link)

        user_a.notify(NEW_GAME)
        user_b.notify(NEW_GAME)
        if randint(0, 1):
            user_a.notify(PLAY_WHITE)
            user_b.notify(PLAY_BLACK)
        else:
            user_a.notify(PLAY_BLACK)
            user_b.notify(PLAY_WHITE)

    def __main_loop(self) -> None:
        user: User
        last_link = 0.0
        reversed_sort = True

        db = Database(self.DATABASE_FILENAME)
        users, max_id = db.get_users()
        User.set_id(max_id + 1)
        self._all_users.update(users)
        db.close()

        while not self._stop:
            t0 = time.time()
            for user in self._online_users:
                try:
                    user.receive_message()
                except BlockingIOError:
                    continue
                except ConnectionError:
                    logging.info('CONNECTION ERROR (RECEIVING DATA FROM ' + user.get_name() + ')')
                    self._disconnected_users.add(user)
                    continue
                except OSError:
                    logging.info('OS ERROR (RECEIVING DATA FROM ' + user.get_name() + ')')
                    self._disconnected_users.add(user)
                    traceback.print_exc()
                    continue
                except Exception as ex:
                    logging.error(str(ex))

            self.__remove_disconnected_users()
            self.__process_messages()
            self.__remove_disconnected_users()
            self.__add_users()

            if time.time() - last_link > Server.LINK_INTERVAL:  # link players every LINK_INTERVAL seconds
                reversed_sort = not reversed_sort
                self._unlinked_users.clear()
                self._unlinked_users.update(self._users_to_link - set(self._linked_users))
                unlinked_list = list(self._unlinked_users)
                # sort by rating. connect users with similarly high rating:
                unlinked_list.sort(key=lambda c: c.rating, reverse=reversed_sort)
                unlinked_count = len(unlinked_list)
                for i in range(unlinked_count // 2):
                    self.__link_users(unlinked_list[2 * i], unlinked_list[2 * i + 1])
                last_link = time.time()

            self._admin: User
            if self._admin:
                try:
                    self._admin.receive_message()
                except BlockingIOError:
                    pass
                except ConnectionError:
                    logging.info('CONNECTION ERROR (RECEIVING DATA FROM ADMIN)')
                    self._admin.socket.close()
                    self._admin = None
                except OSError as ex:
                    logging.error('OS ERROR (RECEIVING DATA FROM ADMIN)')
                    logging.error(str(ex))
                    self._admin.socket.close()
                    self._admin = None

            t1 = time.time()
            time_limit = 0.05
            if t1 - t0 > time_limit:
                # loop cycle lasted more than 50ms - will most likely not happen
                logging.info('time limit exceeded')
                continue
            else:
                time.sleep(time_limit)

        logging.info(self.SOCKET_NAME + ' main loop interrupted')
        logging.info(self.execute('update'))  # database update
