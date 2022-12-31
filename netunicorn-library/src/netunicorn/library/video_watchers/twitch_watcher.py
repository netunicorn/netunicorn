"""
Selenium-based Vimeo watcher
"""
import os
import random
import subprocess
import time
from typing import Optional

from netunicorn.base.task import Result, Success, Task, TaskDispatcher
from netunicorn.base.minions import Minion

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service


def watch(url: str, duration: int = 10) -> Result[str, str]:
    display_number = random.randint(100, 500)
    xvfb_process = subprocess.Popen(
        ["Xvfb", f":{display_number}", "-screen", "0", "1920x1080x24"]
    )
    os.environ["DISPLAY"] = f":{display_number}"

    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--autoplay-policy=no-user-gesture-required")
    driver = webdriver.Chrome(service=Service(), options=options)
    time.sleep(1)
    driver.get(url)

    # can't find a way to check whether video is playing now, so let's just wait a timeout
    time.sleep(duration)
    result = Success(f"Video probably finished by timeout: {duration} seconds")
    driver.close()
    xvfb_process.kill()
    return result


class WatchTwitchStream(TaskDispatcher):
    def __init__(self, video_url: str, duration: Optional[int] = None):
        self.video_url = video_url
        self.duration = duration
        super().__init__()

    def dispatch(self, minion: Minion) -> Task:
        if minion.properties.get("os_family", "").lower() == "linux":
            return WatchTwitchStreamLinuxImplementation(self.video_url, self.duration)

        raise NotImplementedError(
            f'WatchYouTubeVideo is not implemented for {minion.properties.get("os_family", "")}'
        )


class WatchTwitchStreamLinuxImplementation(Task):
    requirements = [
        "sudo apt update",
        "sudo apt install -y python3-pip wget xvfb",
        "pip3 install selenium webdriver-manager",
        "wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb",
        "sudo apt install -y ./google-chrome-stable_current_amd64.deb",
        "sudo apt install -y -f",
        'python3 -c "from webdriver_manager.chrome import ChromeDriverManager; ChromeDriverManager(path="/usr/bin/").install()"',
    ]

    def __init__(self, video_url: str, duration: int = 10):
        self.video_url = video_url
        self.duration = duration
        super().__init__()

    def run(self):
        return watch(self.video_url, self.duration)


if __name__ == "__main__":
    print(watch("https://www.twitch.tv/videos/1592059689", 10))
