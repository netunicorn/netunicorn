import utils.minion_handler
import utils.minion_pool

addresses = [
    "google.com",
    "csworld52.cs.ucsb.edu",  # Border router
    "137.164.23.90",  # Last router
    "twitter.com"
]
minions = utils.minion_pool.MinionPool().get()
for minion in minions:
    for address in addresses:
        ping = minion.ping(address, 5, upload=True)
    minion.speed_test(upload=True)
