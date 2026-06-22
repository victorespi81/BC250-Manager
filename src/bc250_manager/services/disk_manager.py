from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SUPPORTED_FILESYSTEMS = frozenset({"ext4", "btrfs", "xfs", "ntfs", "ntfs3", "exfat"})
IGNORED_FILESYSTEMS = frozenset({"swap", "vfat"})
IGNORED_MOUNTPOINTS = frozenset({"/", "/boot"})


@dataclass(frozen=True)
class DiskPartition:
    device: str
    size: str
    filesystem: str
    label: str
    uuid: str
    mountpoint: str
    has_steamapps: bool


class DiskDetectionError(RuntimeError):
    """Raised when disk detection cannot complete."""


class DiskManager:
    def list_partitions(self) -> list[DiskPartition]:
        output = self._run_lsblk()
        return self.parse_lsblk_output(output)

    def parse_lsblk_output(self, output: str) -> list[DiskPartition]:
        try:
            payload = json.loads(output)
        except json.JSONDecodeError as exc:
            raise DiskDetectionError("lsblk returned invalid JSON.") from exc

        devices = payload.get("blockdevices")
        if not isinstance(devices, list):
            raise DiskDetectionError("lsblk output does not contain block devices.")

        partitions: list[DiskPartition] = []
        for device in devices:
            partitions.extend(self._collect_partitions(device))

        return partitions

    def _run_lsblk(self) -> str:
        command = [
            "lsblk",
            "-J",
            "-o",
            "NAME,PATH,SIZE,FSTYPE,LABEL,UUID,MOUNTPOINTS,TYPE",
        ]

        try:
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as exc:
            raise DiskDetectionError("lsblk is not available on this system.") from exc
        except subprocess.CalledProcessError as exc:
            message = exc.stderr.strip() or "lsblk failed to detect partitions."
            raise DiskDetectionError(message) from exc

        return completed.stdout

    def _collect_partitions(self, node: dict[str, Any]) -> list[DiskPartition]:
        partitions: list[DiskPartition] = []

        if node.get("type") == "part" and self._is_supported_partition(node):
            partitions.append(self._partition_from_node(node))

        for child in node.get("children") or []:
            if isinstance(child, dict):
                partitions.extend(self._collect_partitions(child))

        return partitions

    def _is_supported_partition(self, node: dict[str, Any]) -> bool:
        filesystem = self._normalize(node.get("fstype"))
        label = self._normalize(node.get("label"))
        mountpoints = self._mountpoints(node)

        if filesystem in IGNORED_FILESYSTEMS:
            return False

        if filesystem not in SUPPORTED_FILESYSTEMS:
            return False

        if label == "efi":
            return False

        return all(mountpoint not in IGNORED_MOUNTPOINTS for mountpoint in mountpoints)

    def _partition_from_node(self, node: dict[str, Any]) -> DiskPartition:
        mountpoint = self._display_mountpoint(node)

        return DiskPartition(
            device=self._value(node.get("path")) or self._device_path(node),
            size=self._value(node.get("size")),
            filesystem=self._value(node.get("fstype")),
            label=self._value(node.get("label")),
            uuid=self._value(node.get("uuid")),
            mountpoint=mountpoint,
            has_steamapps=self._has_steamapps(mountpoint),
        )

    def _device_path(self, node: dict[str, Any]) -> str:
        name = self._value(node.get("name"))
        if not name:
            return ""

        return name if name.startswith("/dev/") else f"/dev/{name}"

    def _display_mountpoint(self, node: dict[str, Any]) -> str:
        mountpoints = self._mountpoints(node)
        return mountpoints[0] if mountpoints else ""

    def _mountpoints(self, node: dict[str, Any]) -> list[str]:
        raw_mountpoints = node.get("mountpoints")

        if isinstance(raw_mountpoints, list):
            return [mountpoint for mountpoint in raw_mountpoints if isinstance(mountpoint, str)]

        raw_mountpoint = node.get("mountpoint")
        if isinstance(raw_mountpoint, str):
            return [raw_mountpoint]

        return []

    def _has_steamapps(self, mountpoint: str) -> bool:
        if not mountpoint:
            return False

        return (Path(mountpoint) / "steamapps").is_dir()

    def _normalize(self, value: Any) -> str:
        return self._value(value).lower()

    def _value(self, value: Any) -> str:
        return value if isinstance(value, str) else ""
