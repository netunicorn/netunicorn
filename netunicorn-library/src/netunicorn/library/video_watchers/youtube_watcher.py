"""
Selenium-based YouTube watcher
"""
import os
import random
import subprocess
import time
from typing import Optional
from enum import IntEnum

from netunicorn.base.task import Result, Failure, Success, Task, TaskDispatcher
from netunicorn.base.nodes import Node

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys


class YouTubeIFrameStatus(IntEnum):
    UNSTARTED = -1
    ENDED = 0
    PLAYING = 1
    PAUSED = 2
    BUFFERING = 3
    CUED = 5


def watch(
    url: str, duration: Optional[int] = 100, chrome_location: Optional[str] = None
) -> Result[str, str]:
    display_number = random.randint(100, 500)
    xvfb_process = subprocess.Popen(
        ["Xvfb", f":{display_number}", "-screen", "0", "1920x1080x24"]
    )
    os.environ["DISPLAY"] = f":{display_number}"

    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--autoplay-policy=no-user-gesture-required")
    if chrome_location:
        options.binary_location = chrome_location
    driver = webdriver.Chrome(service=Service(), options=options)
    time.sleep(1)
    driver.get(url)
    video = driver.find_element(By.ID, "movie_player")

    player_status = driver.execute_script(
        "return document.getElementById('movie_player').getPlayerState()"
    )
    if player_status is None:
        driver.close()
        xvfb_process.kill()
        return Failure("Failed to get player status")

    while player_status == YouTubeIFrameStatus.BUFFERING:
        time.sleep(1)
        player_status = driver.execute_script(
            "return document.getElementById('movie_player').getPlayerState()"
        )

    if player_status in {
        YouTubeIFrameStatus.UNSTARTED,
        YouTubeIFrameStatus.CUED,
        YouTubeIFrameStatus.PAUSED,
    }:
        video.send_keys(Keys.SPACE)
        time.sleep(2)
        player_status = driver.execute_script(
            "return document.getElementById('movie_player').getPlayerState()"
        )
        if player_status != YouTubeIFrameStatus.PLAYING:
            driver.close()
            xvfb_process.kill()
            return Failure("Couldn't start the video: unknown error")

    if duration:
        time.sleep(duration)
        result = Success(f"Video finished by timeout: {duration} seconds")
    else:
        while player_status in {
            YouTubeIFrameStatus.PLAYING,
            YouTubeIFrameStatus.BUFFERING,
        }:
            time.sleep(2)
            player_status = driver.execute_script(
                "return document.getElementById('movie_player').getPlayerState()"
            )
        result = Success("Video finished by reaching the end")

    driver.close()
    xvfb_process.kill()
    return result


class WatchYouTubeVideo(TaskDispatcher):
    def __init__(self, video_url: str, duration: Optional[int] = None):
        self.video_url = video_url
        self.duration = duration
        super().__init__()

    def dispatch(self, node: Node) -> Task:
        if node.properties.get("os_family", "").lower() == "linux":
            return WatchYouTubeVideoLinuxImplementation(self.video_url, self.duration)

        raise NotImplementedError(
            f'WatchYouTubeVideo is not implemented for {node.properties.get("os_family", "")}'
        )


class WatchYouTubeVideoLinuxImplementation(Task):
    requirements = [
        "sudo apt update",
        "sudo apt install -y python3-pip wget xvfb",
        "pip3 install selenium webdriver-manager",
        "sudo apt install -y chromium-browser",
        "python3 -c \"from webdriver_manager.chrome import ChromeDriverManager; from webdriver_manager.core.utils import ChromeType; ChromeDriverManager(chrome_type=ChromeType.CHROMIUM,path='/usr/bin/').install()\"",
    ]

    def __init__(
        self,
        video_url: str,
        duration: Optional[int] = None,
        chrome_location: Optional[str] = None,
    ):
        self.video_url = video_url
        self.duration = duration
        self.chrome_location = chrome_location
        if not self.chrome_location:
            self.chrome_location = "/usr/bin/chromium-browser"
        super().__init__()

    def run(self):
        return watch(self.video_url, self.duration, self.chrome_location)


if __name__ == "__main__":
    print(watch("https://www.youtube.com/watch?v=dQw4w9WgXcQ", 10))
