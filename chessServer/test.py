import os
import threading
import time
import unittest
import warnings

from chessServer import Client
from chessServer import Server


class TestServer(unittest.TestCase):

    def setUp(self):
        warnings.simplefilter('ignore', category=ResourceWarning)
        self.port = 55555
        self.ip = '127.0.0.99'
        Server.LINK_INTERVAL = 0  # link users immediately
        Server.DB_UPDATE_INTERVAL = 1
        self.server = Server(self.ip, self.port, 'auth', 'pw')
        self.server.run()
        self.clients = list()
        time.sleep(0.1)

    def runTest(self):
        self.choose_port()
        self.register_clients()
        self.notify_clients()
        self.link_to_user()

    def choose_port(self):
        self.assertGreaterEqual(self.server.get_port(), self.port)
        self.assertLessEqual(self.server.get_port(), self.port + Server.MAX_ATTEMPTS)

    def register_clients(self):
        port = self.server.get_port()
        for i in range(10):
            self.clients.append(Client(hostname=self.ip,
                                       port=port,
                                       authentication='auth',
                                       name='client_' + str(i),
                                       password='myPw',
                                       terminal_mode=False))

        for n in range(5):
            self.clients[n].send('%SERVER LINK')

        time.sleep(0.3)
        self.assertEqual(10, len(self.server._all_users), 'users not registered correctly')
        self.assertEqual(len(self.server._linked_users), 4, 'users not linked correctly')
        self.assertEqual(len(self.server._users_to_link), 1, 'users not linked correctly')

    def notify_clients(self):
        client = self.clients[9]
        self.server.execute('notify client_9 have a nice day!')
        self.assertEqual(client.next_message(), 'WELCOME client_9')
        self.assertEqual(client.next_message(), 'have a nice day!')

    def link_to_user(self):
        client_7 = self.clients[7]
        client_6 = self.clients[6]
        time.sleep(0.1)
        client_6.send('%SERVER BLABLABLA THROW EXCEPTION')
        client_7.send('%SERVER NO VALID ARG')
        client_7.send('%SERVER LINKTO client_6')
        time.sleep(0.1)

        self.assertEqual(client_7.next_message(), 'WELCOME client_7')
        self.assertEqual(client_7.next_message(), '%NAME client_6')
        self.assertTrue(client_7.next_message().startswith('%NOTE'))
        self.assertTrue(client_7.next_message().startswith('%MOVE'))
        self.assertTrue(client_6.next_message().startswith('WELCOME'))
        self.assertTrue(client_6.next_message().startswith('%NAME'))
        self.assertTrue(client_6.next_message().startswith('%NOTE'))
        self.assertTrue(client_6.next_message().startswith('%MOVE'))

    def tearDown(self):
        self.server.stop()

        while threading.activeCount() > 2:
            time.sleep(0.1)
        os.remove(self.server.DATABASE_FILENAME)
