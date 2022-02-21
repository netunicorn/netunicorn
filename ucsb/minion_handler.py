from subprocess import Popen, PIPE
import salt.client
import validators
import statistics
import re


class MinionHandler:
    local = salt.client.LocalClient()
    project_path = "/home/ubuntu/active-measurements/"
    _git = "git --git-dir={0}.git --work-tree={0}".format(project_path)

    def __init__(self, minion_id):
        if not isinstance(minion_id, str):
            raise Exception(minion_id + " is not a string")

        self.minion_id = minion_id

    @staticmethod
    def validate_address(address):
        if validators.url(address):
            return True
        if validators.domain(address):
            return True
        if validators.ip_address.ipv4(address):
            return True

        return False

    @staticmethod
    def parse_ping_output(output):
        ping_output = []
        lines = output.splitlines()
        for line in lines:
            if line.strip().startswith("64"):
                ping_output.append(re.findall(r'\d+\.*\d*', line)[-1])

        return [float(v) for v in ping_output]

    def runCommand(self, command):
        print("running: ", command, " on:", self.minion_id)
        output = self.local.cmd(self.minion_id, 'cmd.run', [command])
        return output[self.minion_id]

    def updateCode(self):
        print(self.runCommand(self._git + " pull"))

    def runYoutubeExperiment(self):
        print(self.runCommand('python3 {}ucsb/selenium_scripts/youtube_video.py'
                              .format(self.project_path)))

    def ping(self, address, count=1):
        address = address.strip()
        validation = MinionHandler.validate_address(address)
        if not validation:
            raise Exception("invalid address {}".format(address))
        if not isinstance(count, int):
            raise Exception("count should be an integer")

        ping_output = self.runCommand("ping {} -c {}".format(address, count))
        ping_output = MinionHandler.parse_ping_output(ping_output)
        if len(ping_output) == 0:
            raise Exception("Ping error")
        return statistics.mean(ping_output)
