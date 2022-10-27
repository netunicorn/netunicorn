import os
import subprocess
import time
from typing import Optional

from jinja2 import Environment, FileSystemLoader
from netunicorn.base.minions import Minion
from netunicorn.base.task import Failure, Success, Task, TaskDispatcher


class StartQoECollectionServer(TaskDispatcher):
    def __init__(
        self, data_folder: str = ".", interface: str = "0.0.0.0", port: int = 34543
    ):
        self.data_folder = data_folder
        self.interface = interface
        self.port = port
        super().__init__()

    def dispatch(self, minion: Minion) -> Task:
        if minion.properties.get("os_family", "").lower() == "linux":
            return StartQoECollectionServerLinuxImplementation(
                self.data_folder, self.interface, self.port
            )

        raise NotImplementedError(
            f'StartQoECollectionServer is not implemented for {minion.properties.get("os_family", "")}'
        )


class StartQoECollectionServerLinuxImplementation(Task):
    requirements = [
        "sudo apt-get update",
        "sudo apt-get install -y python3-pip uvicorn",
        "pip3 install fastapi uvicorn uvloop",
    ]

    def __init__(
        self, data_folder: str = ".", interface: str = "0.0.0.0", port: int = 34543
    ):
        self.data_folder = data_folder
        self.interface = interface
        self.port = port
        super().__init__()

    def run(self):
        env = os.environ.copy()
        env["QOE_DATA_FOLDER"] = self.data_folder

        process = subprocess.Popen(
            [
                "uvicorn",
                "netunicorn.library.qoe_youtube.qoe_collector:app",
                "--host",
                self.interface,
                "--port",
                str(self.port),
                "--log-level",
                "warning",
            ],
            env=env,
        )
        time.sleep(3)

        if (exitcode := process.poll()) is not None:
            return Failure(
                f"QoE collection server failed to start: exitcode={exitcode}"
            )

        return (
            f"QoE collection server started with data folder '{self.data_folder}' and "
            f"using interface {self.interface}:{self.port}, process ID: {process.pid}",
            process.pid,
        )


class StopQoECollectionServer(TaskDispatcher):
    def dispatch(self, minion: Minion) -> Task:
        if minion.properties.get("os_family", "").lower() == "linux":
            return StopQoECollectionServerLinuxImplementation()

        raise NotImplementedError(
            f'StopQoECollectionServer is not implemented for {minion.properties.get("os_family", "")}'
        )


class StopQoECollectionServerLinuxImplementation(Task):
    def run(self):
        # look for the process ID of the QoE collection server and use it to kill the server
        for element in self.previous_steps:
            if isinstance(element, Success):
                element = [element]
            for result in element:
                if isinstance(y := result.unwrap(), tuple) and str(y[0]).startswith(
                    "QoE collection server started"
                ):
                    process_id = y[1]
                    subprocess.run(["kill", str(process_id)])
                    return Success(
                        f"QoE collection server stopped with process ID: {process_id}"
                    )
        return Failure("QoE collection server not found")


class WatchYouTubeVideo(TaskDispatcher):
    def __init__(
        self,
        video_url: str,
        duration: Optional[int] = None,
        quality: Optional[int] = None,
        qoe_server_address: str = "localhost",
        qoe_server_port: int = 34543,
        report_time: int = 250,
    ):
        self.video_url = video_url
        self.duration = duration
        self.quality = quality
        self.qoe_server_address = qoe_server_address
        self.qoe_server_port = qoe_server_port
        self.report_time = report_time
        super().__init__()

    def dispatch(self, minion: Minion) -> Task:
        if minion.properties.get("os_family", "").lower() == "linux":
            return WatchYouTubeVideoLinuxImplementation(
                self.video_url,
                self.duration,
                self.quality,
                self.qoe_server_address,
                self.qoe_server_port,
                self.report_time,
            )

        raise NotImplementedError(
            f'WatchYouTubeVideo is not implemented for {minion.properties.get("os_family", "")}'
        )


class WatchYouTubeVideoLinuxImplementation(Task):
    requirements = [
        "sudo apt update",
        "sudo apt install -y python3-pip wget xvfb unzip",
        "pip3 install selenium webdriver-manager Jinja2==3.0.1",
        "wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb",
        "sudo apt install -y ./google-chrome-stable_current_amd64.deb",
        "sudo apt install -y -f",
        'python3 -c "from webdriver_manager.chrome import ChromeDriverManager; ChromeDriverManager(path="/usr/bin/").install()"',
        "wget https://github.com/nectostr/pinot_minion_tasks/raw/collection/QoE_youtube/extensions/4.46.2_0.crx -P ./extensions",
        "wget https://github.com/nectostr/pinot_minion_tasks/releases/download/public/qoe_extension.zip -P ./extensions",
        "unzip ./extensions/qoe_extension.zip -d ./extensions/qoe_extension",
    ]

    def __init__(
        self,
        video_url: str,
        duration: Optional[int] = None,
        quality: Optional[int] = None,
        qoe_server_address: str = "localhost",
        qoe_server_port: int = 34543,
        report_time: int = 250,
    ):
        self.video_url = video_url
        self.duration = duration
        self.quality = quality
        self.qoe_server_address = qoe_server_address
        self.qoe_server_port = qoe_server_port
        self.report_time = report_time
        super().__init__()

    def run(self):
        from netunicorn.library.qoe_youtube import qoe_collector, watcher

        adblock_crx_path = os.path.join(".", "extensions", "4.46.2_0.crx")
        qoe_extension_path = os.path.join(".", "extensions", "qoe_extension")

        # using jinja substitute QoECollectionServer address and port in script.json
        env = Environment(loader=FileSystemLoader(qoe_extension_path))
        template = env.get_template("script.js.template")
        output = template.render(
            server_address=self.qoe_server_address,
            server_port=self.qoe_server_port,
            report_time=self.report_time,
        )
        with open(os.path.join(qoe_extension_path, "script.js"), "w") as f:
            f.write(output)

        # set STATSFORNERDS_PATH and ADBLOCK_PATH variables
        watcher.STATSFORNERDS_PATH = qoe_extension_path
        watcher.ADBLOCK_PATH = adblock_crx_path

        # run watcher
        return watcher.watch(self.video_url, self.duration, self.quality)
