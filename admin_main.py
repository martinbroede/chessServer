import sys

from chessServer import Admin
from chessServer import get_local_ip

if __name__ == '__main__':

    arguments = [_admin_authentication, _hostname, _port] = [None, None, None]

    for i in range(len(sys.argv) - 1):
        arguments[i] = sys.argv[i + 1]

    [_admin_authentication, _hostname, _port] = arguments

    if not _admin_authentication:
        _admin_authentication = input('enter password:')
    if not _hostname:
        _hostname = input('enter address you want to connect with:')
    if not _port:
        _port = input('enter port number:')
    if _hostname == 'local':
        _hostname = get_local_ip()

    print(f'admin - connect to: {_hostname} / port: {_port}')
    print('authentication:')
    print('*' * len(_admin_authentication))

    Admin(_hostname, _port, _admin_authentication)
