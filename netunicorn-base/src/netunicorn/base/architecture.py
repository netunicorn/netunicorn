"""
Architecture information about nodes.
"""
from enum import Enum


class Architecture(Enum):
    """
    Enumerate possible node architectures.
    """

    LINUX_AMD64 = "linux/amd64"
    """
    AMD64-based Linux node.
    """

    LINUX_ARM64 = "linux/arm64"
    """
    AMR64-based Linux node.
    """

    UNKNOWN = "unknown"
    """
    Unknown architecture and operating system.
    """
