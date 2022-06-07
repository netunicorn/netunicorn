import subprocess
import time
import os
from typing import Optional

from jinja2 import Environment, FileSystemLoader

from pinot.base.task import Task, Failure
from pinot.library.qoe_youtube import qoe_collector, watcher


class StartQoECollectionServer(Task):
    requirements = [
        'sudo apt update',
        'sudo apt install python3-pip',
        'pip3 install fastapi uvicorn',
    ]

    def __init__(self, data_folder: str = '.', interface: str = '0.0.0.0', port: int = 34543):
        self.data_folder = data_folder
        self.interface = interface
        self.port = port
        super().__init__()

    def run(self):
        env = os.environ.copy()
        env['QOE_DATA_FOLDER'] = self.data_folder

        process = subprocess.Popen([
            'uvicorn', 'pinot.library.qoe_youtube.qoe_collector:app',
            '--host', self.interface, '--port', str(self.port),
        ], env=env)
        time.sleep(3)

        if (exitcode := process.poll()) is not None:
            return Failure(f'QoE collection server failed to start: exitcode={exitcode}')

        return f"QoE collection server started with data folder '{self.data_folder}' and " \
               f"using interface {self.interface}:{self.port}"


class StopQoECollectionServer(Task):
    def run(self):
        # TODO: implement
        raise NotImplementedError()


class WatchYouTubeVideo(Task):
    requirements = [
        'sudo apt update',
        'sudo apt install -y python3-pip wget Xvfb unzip',
        'pip3 install selenium webdriver-manager Jinja2',
        'wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb',
        'sudo apt install ./google-chrome-stable_current_amd64.deb',
        'sudo apt install -f',
        'python3 -c "import webdriver_manager; webdriver_manager.chromedriver.install()"',
    ]

    def __init__(
            self, video_url: str, duration: Optional[int] = None, quality: Optional[int] = None,
            qoe_server_address: str = 'localhost', qoe_server_port: int = 34543, report_time: int = 250,
    ):
        self.video_url = video_url
        self.duration = duration
        self.quality = quality
        self.qoe_server_address = qoe_server_address
        self.qoe_server_port = qoe_server_port
        self.report_time = report_time
        super().__init__()

    def run(self):
        # download adblock.crx and remember path
        subprocess.Popen([
            'wget',
            'https://github.com/nectostr/pinot_minion_tasks/raw/collection/QoE_youtube/extensions/4.46.2_0.crx',
            '-P', './extensions',
        ]).wait()
        adblock_crx_path = os.path.join('.', 'extensions', '4.46.2_0.crx')

        # download QoE extension
        subprocess.Popen([
            'wget',
            'https://github.com/nectostr/pinot_minion_tasks/releases/download/public/qoe_extension.zip',
            '-P', './extensions',
        ]).wait()
        subprocess.Popen([
            'unzip',
            './extensions/qoe_extension.zip',
            '-d', './extensions/qoe_extension',
        ]).wait()
        qoe_extension_path = os.path.join('.', 'extensions', 'qoe_extension')

        # using jinja substitute QoECollectionServer address and port in script.json
        env = Environment(loader=FileSystemLoader(qoe_extension_path))
        template = env.get_template('script.js.template')
        output = template.render(
            server_address=self.qoe_server_address, server_port=self.qoe_server_port, report_time=self.report_time
        )
        with open(os.path.join(qoe_extension_path, 'script.js'), 'w') as f:
            f.write(output)

        # set STATSFORNERDS_PATH and ADBLOCK_PATH variables
        watcher.STATSFORNERDS_PATH = qoe_extension_path
        watcher.ADBLOCK_PATH = adblock_crx_path

        # run watcher
        return watcher.watch(self.video_url, self.duration, self.quality)
