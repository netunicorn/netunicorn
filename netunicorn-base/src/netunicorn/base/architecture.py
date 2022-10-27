from enum import Enum


class Architecture(Enum):
    LINUX_AMD64 = "linux/amd64"
    LINUX_ARM64 = "linux/arm64"
    UNKNOWN = "unknown"
