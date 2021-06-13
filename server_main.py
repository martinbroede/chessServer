import logging
import sys

from chessServer import Server
from chessServer import get_local_ip

if __name__ == '__main__':

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) > 5:
        print('too many arguments')
        print('args: authentication, admin_authentication, port, ip')
        exit(-1)
    elif len(sys.argv) < 2:
        print('too few arguments')
        print('args: authentication, admin_authentication, port, ip')
        exit(-1)

    server_arguments = [_authentication, _admin_authentication, _port, _ip] = [None, None, None, None]

    for i in range(len(sys.argv) - 1):
        server_arguments[i] = sys.argv[i + 1]

    [_authentication, _admin_authentication, _port, _ip] = server_arguments

    if not _port:
        _port = '55555'
    if not _ip:
        _ip = get_local_ip()

    print(f'server args - ip: {_ip} / port: {_port}')
    print('authentication:')
    print('*' * len(_authentication))
    print('admin authentication:')
    print('*' * len(_admin_authentication))

    server = Server(_ip, _port, _authentication, _admin_authentication)
    server.run()
