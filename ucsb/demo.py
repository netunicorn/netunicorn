import sys

MINION_ID = None
with open('/etc/salt/minion_id', 'r') as f:
    MINION_ID = f.read()
    print('MINION_ID is set to ', MINION_ID)

import utils.minion_handler
import utils.minion_pool
import time

minion = utils.minion_handler.MinionHandler(MINION_ID, in_minion=True)
result = minion.run_command('ping github.com -c 5')

