import os
import subprocess
from typing import Literal, Optional, Set

from netunicorn.base.minions import Architecture, Minion
from netunicorn.base.task import Task, TaskDispatcher


class UploadToWebDav(TaskDispatcher):
    def __init__(
        self,
        filepaths: Set[str],
        endpoint: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        authentication: Literal["basic"] = "basic",
    ):
        if endpoint[-1] == "/":
            endpoint = endpoint[:-1]
        self.filepaths = filepaths
        self.endpoint = endpoint
        self.username = username
        self.password = password
        self.authentication = authentication

        super().__init__()

    def dispatch(self, minion: Minion) -> Task:
        result = UploadToWebDavImplementation(
            self.filepaths,
            self.endpoint,
            self.username,
            self.password,
            self.authentication,
        )

        if minion.architecture in {Architecture.LINUX_AMD64, Architecture.LINUX_ARM64}:
            result.requirements = ["sudo apt-get install -y curl"]
            return result

        raise NotImplementedError(
            f"UploadToWebDav is not implemented for {minion.architecture}"
        )


class UploadToWebDavImplementation(Task):
    def __init__(
        self,
        filepaths: Set[str],
        endpoint: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        authentication: Literal["basic"] = "basic",
    ):
        self.filepaths = filepaths
        self.endpoint = endpoint
        self.username = username
        self.password = password
        self.authentication = authentication
        super().__init__()

    def run(self):
        executor_id = os.environ.get("NETUNICORN_EXECUTOR_ID") or "Unknown"

        for file in self.filepaths:
            command = ["curl", "-T", file, f"{self.endpoint}/{executor_id}/{file}"]
            if self.authentication == "basic":
                command += ["--user", f"{self.username}:{self.password}", "--basic"]
            subprocess.run(command, check=True)
        return f"Successfully uploaded to {self.endpoint} files: {self.filepaths}"
