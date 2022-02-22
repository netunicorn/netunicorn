from subprocess import Popen, PIPE
from influxdb import InfluxDBClient
from time import gmtime, strftime
import salt.client
import validators
import statistics
import re


class MinionHandler:
    local = salt.client.LocalClient()
    project_path = "/home/ubuntu/active-measurements/"
    _git = "git --git-dir={0}.git --work-tree={0}".format(project_path)
    client = None

    def __init__(self, minion_id):
        if not isinstance(minion_id, str):
            raise Exception(minion_id + " is not a string")

        self.minion_id = minion_id
        self.client = InfluxDBClient(host='snl-server-3.cs.ucsb.edu', port=8086, username='admin', password='ucsbsnl!!',
                                     ssl=True, verify_ssl=True)
        self.client.switch_database('netrics1')

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

    def _upload_ping_result(self, address, ping):
        if not address:
            raise Exception("address cannot be empty")
        if not isinstance(ping, float):
            raise Exception("ping is not a valid number: {}".format(ping))

        return self.client.write_points([{
            "measurement": "networks",
            "tags": {
                "user": self.minion_id,
            },
            "time": strftime("%Y-%m-%dT%H:%M:%SZ", gmtime()),
            "fields": {
                "ping_to_{}".format(address): ping
            }
        }])

    def _upload_speedtest_result(self, download, upload):
        if not isinstance(download, float) or not isinstance(upload, float):
            raise Exception("download/upload is not a valid number: {}/{}".format(download, upload))

        return self.client.write_points([{
            "measurement": "networks",
            "tags": {
                "user": self.minion_id,
            },
            "time": strftime("%Y-%m-%dT%H:%M:%SZ", gmtime()),
            "fields": {
                "speedtest_download": download
            }
        }, {
            "measurement": "networks",
            "tags": {
                "user": self.minion_id,
            },
            "time": strftime("%Y-%m-%dT%H:%M:%SZ", gmtime()),
            "fields": {
                "speedtest_upload": upload
            }
        }])

    def runCommand(self, command):
        print("running: ", command, " on:", self.minion_id)
        output = self.local.cmd(self.minion_id, 'cmd.run', [command])
        return output[self.minion_id]

    def isUp(self):
        status = self.local.cmd(self.minion_id, 'test.ping')[self.minion_id]
        return status

    def updateCode(self):
        print(self.runCommand(self._git + " pull"))

    def runYoutubeExperiment(self):
        print(self.runCommand('python3 {}ucsb/selenium_scripts/youtube_video.py'
                              .format(self.project_path)))

    def ping(self, address, count=1, upload=False):
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

        mean_ping = statistics.mean(ping_output)
        if upload:
            self._upload_ping_result(address, mean_ping)
        return mean_ping

    def speed_test(self, upload=False):
        output = self.runCommand("speedtest-cli --simple")
        speedtest_output = []
        lines = output.splitlines()
        for line in lines:
            speedtest_output.append(float(re.findall(r'\d+\.*\d*', line)[0]))
        if upload:
            self._upload_speedtest_result(speedtest_output[1], speedtest_output[2])
        return speedtest_output[1], speedtest_output[2]
