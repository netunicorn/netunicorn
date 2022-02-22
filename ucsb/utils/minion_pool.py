import random

import utils.minion_handler

minion_ids = [
    "raspi-2",
    "raspi-5"
]

class MinionPool:
    minions = []

    def __init__(self):
        for m_id in minion_ids:
            m_id = m_id.strip()
            minion = utils.minion_handler.MinionHandler(m_id)
            if minion.isUp():
                self.minions.append(minion)
                print(m_id)

    def get(self, count=0):
        if not isinstance(count, int):
            raise Exception("count should be an integer")
        if count == 0 or count >= len(self.minions):
            return self.minions
        return random.sample(self.minions, count)
