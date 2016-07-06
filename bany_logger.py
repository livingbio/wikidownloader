from sys      import exit, stdout
from datetime import datetime as dt
from socket   import gethostname
import logging

def setLogger(fileNameBase = '', streamOut = stdout):
    """Enable logging to a file and standard output
    
    fileNameBase: Set None to disable file logger. Set a string to enable.
    streamOut: Set None to disable stream output. Set sys.stdout to enbable.
    """
    fmtstr = '%(asctime)s [%(levelname)s][%(name)s] %(message)s'
    datefmtstr = '%Y-%m-%d %H:%M:%S'
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # log to file
    if fileNameBase is not None:
        log_fn = str(dt.now().date()) + '-' + fileNameBase + '.txt'
        logHandler = logging.FileHandler(log_fn)
        logger.addHandler(logHandler)
        logHandler.setFormatter(logging.Formatter(fmtstr, datefmtstr))

    # log to stdout
    if streamOut:
        logHandler = logging.StreamHandler(stdout)
        logger.addHandler(logHandler)
        logHandler.setFormatter(logging.Formatter(fmtstr, datefmtstr))


import unittest
from os import remove

class TestLoggerMethods(unittest.TestCase):
    """Unit test module and examples
    """
    def test_logger_file(self):
        """setLogger('unit-test')
        """
        setLogger('unit-test', None)
        logging.info('hello')
        logging.warn('world')
        log_fn = str(dt.now().date()) + '-unit-test.txt'
        with open(log_fn, 'r') as f:
            lines = f.read().splitlines()
            self.assertEqual(lines[0][-18:], '[INFO][root] hello')
            self.assertEqual(lines[1][-21:], '[WARNING][root] world')
        for h in logging.getLogger().handlers:
            h.close()
        remove(log_fn)


if __name__ == '__main__':
    unittest.main()

