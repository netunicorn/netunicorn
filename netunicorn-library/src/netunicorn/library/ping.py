import subprocess
from dataclasses import dataclass
from typing import List

from netunicorn.base.minions import Minion
from netunicorn.base.task import Failure, Task, TaskDispatcher


@dataclass
class PacketResult:
    icmp_seq: int
    ttl: int
    time: float
    unit: str


@dataclass
class PingResult:
    host: str
    packets: List[PacketResult]
    packet_loss: float
    min_rtt: float
    avg_rtt: float
    max_rtt: float
    stddev_rtt: float
    unit_rtt: str
    unparsed_output: List[str]
    raw_output: str


class Ping(TaskDispatcher):
    def __init__(self, address: str, count: int = 1):
        self.address = address
        self.count = count
        super().__init__()

    def dispatch(self, minion: Minion) -> Task:
        if minion.properties.get("os_family", "").lower() == "linux":
            return PingLinuxImplementation(self.address, self.count)
        raise NotImplementedError(
            f'Ping is not implemented for {minion.properties.get("os_family", "")}'
        )


class PingLinuxImplementation(Task):
    requirements = ["sudo apt-get install -y inetutils-ping"]

    def __init__(self, address: str, count: int = 1):
        super().__init__()
        self.address = address.strip()
        self.count = count

    def run(self):
        result = subprocess.run(
            ["ping", self.address, "-c", str(self.count)], capture_output=True
        )
        if result.returncode != 0:
            return Failure(
                result.stdout.decode("utf-8").strip()
                + "\n"
                + result.stderr.decode("utf-8").strip()
            )

        return self._format(result.stdout.decode("utf-8"))

    def _format(self, output: str) -> PingResult:
        raw_output = output[:]
        lines = [x for x in output.split("\n") if x]
        if not lines[-1].startswith("round-trip"):
            return PingResult(self.address, [], 100, 0, 0, 0, 0, "", [], raw_output)

        # parse rtt statistics
        rtts, unit = lines[-1].split("=")[1].strip().split(" ")
        rtt_min, rtt_avg, rtt_max, rtt_stddev = [float(x) for x in rtts.split("/")]
        lines = lines[:-1]

        # take packet_loss line and packets received
        packets_received, packet_loss = lines[-1].split(",")[1:]
        packets_received = int(packets_received.strip().split(" ")[0])
        packet_loss = float(packet_loss.strip().split("%")[0])
        lines = lines[:-1]

        # remove first and last line
        lines = lines[1:-1]

        # parse received packets
        packets = []
        for packet in lines[:packets_received]:
            packet = packet.split(":")[1]
            seq, ttl, time, unit = [x.strip() for x in packet.split(" ") if x]
            seq = int(seq.split("=")[1])
            ttl = int(ttl.split("=")[1])
            time = float(time.split("=")[1])
            packets.append(PacketResult(seq, ttl, time, unit))
        lines = lines[packets_received:]

        # theoretically, here should be 0 lines left
        unparsed_output = lines

        return PingResult(
            self.address,
            packets,
            packet_loss,
            rtt_min,
            rtt_avg,
            rtt_max,
            rtt_stddev,
            unit,
            unparsed_output,
            raw_output,
        )
