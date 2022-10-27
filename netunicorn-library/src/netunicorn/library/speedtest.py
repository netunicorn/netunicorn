import subprocess
from typing import Dict

from netunicorn.base.minions import Minion
from netunicorn.base.task import Failure, Task, TaskDispatcher


class SpeedTest(TaskDispatcher):
    def dispatch(self, minion: Minion) -> Task:
        if minion.properties.get("os_family", "").lower() == "linux":
            return SpeedTestLinuxImplementation()

        raise NotImplementedError(
            f'SpeedTest is not implemented for {minion.properties.get("os_family", "")}'
        )


class SpeedTestLinuxImplementation(Task):
    requirements = ["pip install speedtest-cli"]

    def run(self):
        result = subprocess.run(["speedtest-cli", "--simple"], capture_output=True)
        if result.returncode != 0:
            return Failure(
                result.stdout.decode("utf-8").strip()
                + "\n"
                + result.stderr.decode("utf-8").strip()
            )

        return self._format_data(result.stdout.decode("utf-8"))

    @staticmethod
    def _format_data(data: str) -> Dict[str, Dict]:
        ping, download, upload, _ = data.split("\n")
        return {
            "ping": {"value": float(ping.split(" ")[1]), "unit": ping.split(" ")[2]},
            "download": {
                "value": float(download.split(" ")[1]),
                "unit": download.split(" ")[2],
            },
            "upload": {
                "value": float(upload.split(" ")[1]),
                "unit": upload.split(" ")[2],
            },
        }
