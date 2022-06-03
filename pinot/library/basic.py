from pinot.base.task import Task
import time


class DummyTask(Task):
    def run(self):
        return True


class SleepTask(Task):
    def __init__(self, seconds: int):
        self.seconds = seconds
        super().__init__()

    def run(self):
        time.sleep(self.seconds)
        return self.seconds
