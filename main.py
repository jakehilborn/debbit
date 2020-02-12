import logging
import sys
from debbit import debbit

VERSION = 'v1.0.1-dev'

if __name__ == '__main__':
    LOGGER = logging.getLogger('debbit')
    LOGGER.setLevel(logging.INFO)
    log_format = '%(levelname)s: %(asctime)s %(message)s'

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(logging.Formatter(log_format))
    LOGGER.addHandler(stdout_handler)

    file_handler = logging.FileHandler('debbit_log.log')
    file_handler.setFormatter(logging.Formatter(log_format))
    LOGGER.addHandler(file_handler)

    debbit.main()
