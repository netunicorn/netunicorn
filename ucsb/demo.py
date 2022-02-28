import sys

MINION_ID = None
with open('/etc/salt/minion_id', 'r') as f:
    MINION_ID = f.read()
    print('MINION_ID is set to ', MINION_ID)

import utils.minion_handler
import utils.minion_pool
import time

import os

os.system("ping github.com -c 5")