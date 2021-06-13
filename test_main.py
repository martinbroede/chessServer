import logging
import unittest

from chessServer import TestServer

if __name__ == '__main__':
    testServer = TestServer()
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
