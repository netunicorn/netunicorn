import utils.minion_handler
import utils.minion_pool
import time

addresses = [
    "google.com",
    "csworld52.cs.ucsb.edu",  # Border router
    "137.164.23.90",  # Last router
    "twitter.com"
]

last_measurement_time = 0
while True:
    time.sleep(60)
    print("running at {}".format(time.time()))
    minions = utils.minion_pool.MinionPool().get()
    should_get_stats = False
    for minion in minions:
        status = minion.check_youtube_status()
        if time.time() - last_measurement_time > 600 or status is not None and status < 100:
            should_get_stats = True

    last_measurement_time = time.time()
    if should_get_stats:
        for minion in minions:
            for address in addresses:
                ping = minion.ping(address, 5, upload=True)
            minion.speed_test(upload=True)
