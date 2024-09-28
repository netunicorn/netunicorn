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
    ARM64-based Linux node.
    """

    WINDOWS_AMD64 = "win/amd64"
    """
    AMD64-based Windows node.
    """

    WINDOWS_ARM64 = "win/arm64"
    """
    ARM64-based Windows node.
    """

    UNKNOWN = "unknown"
    """
    Unknown architecture and operating system.
    """
