from chessServer.client import Client


class Admin(Client):
    def __init__(self, hostname, port, admin_authentication):
        super(Admin, self).__init__(hostname, port, admin_authentication, 'admin', '')
