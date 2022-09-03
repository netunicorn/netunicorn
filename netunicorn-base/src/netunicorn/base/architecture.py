from enum import Enum


class Architecture(Enum):
    LINUX_64 = "linux/amd64"
    LINUX_ARM64 = "linux/arm64"
    UNKNOWN = "unknown"