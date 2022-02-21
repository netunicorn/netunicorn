import random

from minion_handler import MinionHandler


class MinionPool:
    minions = []

    def __init__(self):
        file: TextIO
        with open("minion_ids", "r") as file:
            for m_id in file:
                m_id = m_id.strip()
                minion = MinionHandler(m_id)
                if minion.isUp():
                    self.minions.append(minion)
                    print(m_id)

    def get(self, count=0):
        if not isinstance(count, int):
            raise Exception("count should be an integer")
        if count == 0 or count >= len(self.minions):
            return self.minions
        return random.sample(self.minions, count)

