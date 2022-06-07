import time
import subprocess
from typing import Optional, List

from pinot.base.task import Task, Failure


class StartCapture(Task):
    requirements = ['sudo apt update', 'sudo apt install tcpdump']

    def __init__(self, filepath: str, arguments: Optional[List[str]] = None):
        self.arguments = arguments or []
        self.filepath = filepath
        super().__init__()

    def run(self):
        proc = subprocess.Popen(["tcpdump"] + self.arguments + ["-U", "-w", self.filepath])
        time.sleep(2)
        if (exit_code := proc.poll()) is None:
            return f"Successfully started tcpdump with filepath={self.filepath}, " \
                   f"additional arguments: {self.arguments}, " \
                   f"process ID: {proc.pid}"

        return Failure(f"Tcpdump terminated with return code {exit_code}")


class StopAllTCPDumps(Task):
    requirements = ['sudo apt update', 'sudo apt install tcpdump']

    def run(self):
        proc = subprocess.Popen(['killall', '-w', 'tcpdump'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = proc.communicate()

        time.sleep(5)  # for tcpdump to finish file
        if out != b"" or err != b"":
            return Failure(
                f"Killall finished with errors.\n"
                f"Stdout: {out},\n"
                f"Stderr: {err}\n"
            )

        return "Successfully killed all tcpdump processes"
