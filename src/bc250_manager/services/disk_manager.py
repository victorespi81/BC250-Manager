from __future__ import annotations

import json
import logging
import re
import shlex
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


SUPPORTED_FILESYSTEMS = frozenset({"ext4", "btrfs", "xfs", "ntfs", "ntfs3", "exfat"})
IGNORED_FILESYSTEMS = frozenset({"iso9660", "swap", "udf", "vfat"})
SYSTEM_MOUNTPOINTS = frozenset(
    {"/", "/boot", "/dev", "/efi", "/home", "/opt", "/proc", "/root", "/run", "/srv", "/sys", "/usr", "/var"}
)
SYSTEM_MOUNTPOINT_PREFIXES = tuple(f"{mountpoint}/" for mountpoint in sorted(SYSTEM_MOUNTPOINTS))
GAME_MOUNTPOINTS = frozenset({"/games"})
GAME_MOUNTPOINT_PREFIXES = tuple(f"{mountpoint}/" for mountpoint in sorted(GAME_MOUNTPOINTS))
FSTAB_PATH = Path("/etc/fstab")
LOG_PATH = Path.home() / ".local" / "state" / "bc250-manager" / "bc250-manager.log"
MOUNT_OPTIONS = "defaults,nofail,x-systemd.device-timeout=5"


@dataclass(frozen=True)
class DiskPartition:
    device: str
    size: str
    filesystem: str
    label: str
    uuid: str
    mountpoint: str
    has_steamapps: bool


@dataclass(frozen=True)
class MountPlan:
    partition: DiskPartition
    target_mountpoint: str
    fstab_line: str
    fstab_entry_exists: bool
    already_mounted: bool


@dataclass(frozen=True)
class MountResult:
    success: bool
    message: str
    plan: MountPlan
    backup_path: str = ""


class DiskDetectionError(RuntimeError):
    """Raised when disk detection cannot complete."""


class DiskManager:
    def __init__(
        self,
        *,
        command_runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
        fstab_path: Path = FSTAB_PATH,
    ) -> None:
        self._command_runner = command_runner or subprocess.run
        self._fstab_path = fstab_path
        self._logger = self._build_logger()

    def list_partitions(self) -> list[DiskPartition]:
        output = self._run_lsblk()
        return self.parse_lsblk_output(output)

    def create_mount_plan(self, partition: DiskPartition) -> MountPlan:
        self._validate_mount_candidate(partition)

        target_mountpoint = self._target_mountpoint(partition)
        fstab_line = self._fstab_line(partition, target_mountpoint)

        return MountPlan(
            partition=partition,
            target_mountpoint=target_mountpoint,
            fstab_line=fstab_line,
            fstab_entry_exists=self._fstab_has_uuid(partition.uuid),
            already_mounted=self._is_game_partition([partition.mountpoint]),
        )

    def mount_partition(self, partition: DiskPartition) -> MountResult:
        plan = self.create_mount_plan(partition)
        self._logger.info("disk selected: %s", partition.device)

        if plan.already_mounted:
            message = f"{partition.device} is already mounted at {partition.mountpoint}."
            self._logger.info("mount success: %s", message)
            return MountResult(success=True, message=message, plan=plan)

        backup_path = self._backup_path()

        try:
            self._run_privileged(["mkdir", "-p", plan.target_mountpoint])

            if not plan.fstab_entry_exists:
                self._run_privileged(["cp", str(self._fstab_path), backup_path])
                self._logger.info("fstab backup path: %s", backup_path)
                self._append_fstab_line(plan.fstab_line)
                self._logger.info("fstab line added: %s", plan.fstab_line)
            else:
                self._logger.info("fstab UUID already exists: %s", partition.uuid)

            self._run_privileged(["systemctl", "daemon-reload"])
            self._run_privileged(["mount", "-a"])
        except DiskDetectionError as exc:
            self._logger.error("mount failure: %s", exc)
            if backup_path and not plan.fstab_entry_exists:
                self._restore_fstab_backup(backup_path)
            return MountResult(
                success=False,
                message=str(exc),
                plan=plan,
                backup_path=backup_path,
            )

        message = f"{partition.device} mounted at {plan.target_mountpoint}."
        self._logger.info("mount success: %s", message)
        return MountResult(success=True, message=message, plan=plan, backup_path=backup_path)

    def parse_lsblk_output(self, output: str) -> list[DiskPartition]:
        try:
            payload = json.loads(output)
        except json.JSONDecodeError as exc:
            raise DiskDetectionError("lsblk returned invalid JSON.") from exc

        devices = payload.get("blockdevices")
        if not isinstance(devices, list):
            raise DiskDetectionError("lsblk output does not contain block devices.")

        root_disk = self._find_root_disk(devices)
        partitions: list[DiskPartition] = []
        for device in devices:
            if isinstance(device, dict):
                partitions.extend(self._collect_partitions(device, root_disk, self._device_id(device)))

        return partitions

    def _run_lsblk(self) -> str:
        command = [
            "lsblk",
            "-J",
            "-o",
            "NAME,PATH,SIZE,FSTYPE,LABEL,UUID,MOUNTPOINTS,TYPE",
        ]

        try:
            completed = self._command_runner(
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

    def _collect_partitions(
        self,
        node: dict[str, Any],
        root_disk: str,
        current_disk: str,
    ) -> list[DiskPartition]:
        partitions: list[DiskPartition] = []

        if node.get("type") == "part" and self._is_supported_partition(node, root_disk, current_disk):
            partitions.append(self._partition_from_node(node))

        for child in node.get("children") or []:
            if isinstance(child, dict):
                partitions.extend(self._collect_partitions(child, root_disk, current_disk))

        return partitions

    def _is_supported_partition(self, node: dict[str, Any], root_disk: str, current_disk: str) -> bool:
        filesystem = self._normalize(node.get("fstype"))
        uuid = self._value(node.get("uuid"))
        mountpoints = self._mountpoints(node)

        if filesystem in IGNORED_FILESYSTEMS:
            return False

        if filesystem not in SUPPORTED_FILESYSTEMS:
            return False

        if not uuid:
            return False

        if any(self._is_system_mountpoint(mountpoint) for mountpoint in mountpoints):
            return False

        if root_disk and current_disk == root_disk and not self._is_game_partition(mountpoints):
            return False

        return True

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

    def _device_id(self, node: dict[str, Any]) -> str:
        return self._value(node.get("path")) or self._device_path(node)

    def _display_mountpoint(self, node: dict[str, Any]) -> str:
        mountpoints = self._mountpoints(node)
        return mountpoints[0] if mountpoints else ""

    def _mountpoints(self, node: dict[str, Any]) -> list[str]:
        raw_mountpoints = node.get("mountpoints")

        if isinstance(raw_mountpoints, list):
            return [
                mountpoint.rstrip("/") or "/"
                for mountpoint in raw_mountpoints
                if isinstance(mountpoint, str) and mountpoint
            ]

        raw_mountpoint = node.get("mountpoint")
        if isinstance(raw_mountpoint, str):
            return [raw_mountpoint.rstrip("/") or "/"] if raw_mountpoint else []

        return []

    def _is_system_mountpoint(self, mountpoint: str) -> bool:
        return mountpoint in SYSTEM_MOUNTPOINTS or mountpoint.startswith(SYSTEM_MOUNTPOINT_PREFIXES)

    def _is_game_partition(self, mountpoints: list[str]) -> bool:
        return any(
            mountpoint in GAME_MOUNTPOINTS or mountpoint.startswith(GAME_MOUNTPOINT_PREFIXES)
            for mountpoint in mountpoints
        )

    def _find_root_disk(self, devices: list[Any]) -> str:
        for device in devices:
            if isinstance(device, dict) and self._contains_mountpoint(device, "/"):
                return self._device_id(device)

        return ""

    def _contains_mountpoint(self, node: dict[str, Any], target: str) -> bool:
        if target in self._mountpoints(node):
            return True

        return any(
            self._contains_mountpoint(child, target)
            for child in node.get("children") or []
            if isinstance(child, dict)
        )

    def _has_steamapps(self, mountpoint: str) -> bool:
        if not mountpoint:
            return False

        return (Path(mountpoint) / "steamapps").is_dir()

    def _validate_mount_candidate(self, partition: DiskPartition) -> None:
        filesystem = partition.filesystem.lower()

        if filesystem not in SUPPORTED_FILESYSTEMS or filesystem in IGNORED_FILESYSTEMS:
            raise DiskDetectionError(f"{partition.filesystem or 'Unknown'} is not supported.")

        if not partition.uuid:
            raise DiskDetectionError("Partition has no UUID.")

        if partition.mountpoint and self._is_system_mountpoint(partition.mountpoint):
            raise DiskDetectionError(f"{partition.mountpoint} is a system mountpoint.")

    def _target_mountpoint(self, partition: DiskPartition) -> str:
        if self._is_game_partition([partition.mountpoint]):
            return partition.mountpoint

        return f"/games/{self._safe_label(partition)}"

    def _safe_label(self, partition: DiskPartition) -> str:
        source = partition.label or partition.uuid
        safe_label = re.sub(r"[^A-Za-z0-9._-]+", "_", source).strip("._-")
        return safe_label or partition.uuid

    def _fstab_line(self, partition: DiskPartition, target_mountpoint: str) -> str:
        return (
            f"UUID={partition.uuid} {target_mountpoint} {partition.filesystem.lower()} "
            f"{MOUNT_OPTIONS} 0 2"
        )

    def _fstab_has_uuid(self, uuid: str) -> bool:
        try:
            contents = self._fstab_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return False
        except OSError as exc:
            raise DiskDetectionError(f"Could not read {self._fstab_path}: {exc}") from exc

        return any(
            line.strip().startswith(f"UUID={uuid}") for line in contents.splitlines()
        )

    def _backup_path(self) -> str:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"{self._fstab_path}.backup.bc250-manager.{timestamp}"

    def _append_fstab_line(self, line: str) -> None:
        script = (
            f"printf '\\n%s\\n' {shlex.quote(line)} >> "
            f"{shlex.quote(str(self._fstab_path))}"
        )
        self._run_privileged(["sh", "-c", script])

    def _restore_fstab_backup(self, backup_path: str) -> None:
        try:
            self._run_privileged(["cp", backup_path, str(self._fstab_path)])
            self._run_privileged(["systemctl", "daemon-reload"])
        except DiskDetectionError as exc:
            self._logger.error("backup restoration failed: %s", exc)
            return

        self._logger.info("backup restoration: %s", backup_path)

    def _run_privileged(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        try:
            return self._command_runner(
                ["pkexec", *command],
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as exc:
            raise DiskDetectionError("pkexec is not available on this system.") from exc
        except subprocess.CalledProcessError as exc:
            message = exc.stderr.strip() or exc.stdout.strip() or "Privileged command failed."
            raise DiskDetectionError(message) from exc

    def _build_logger(self) -> logging.Logger:
        logger = logging.getLogger("bc250_manager.disk_manager")
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            try:
                LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
                handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
            except OSError:
                handler = logging.NullHandler()

            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            logger.addHandler(handler)

        return logger

    def _normalize(self, value: Any) -> str:
        return self._value(value).lower()

    def _value(self, value: Any) -> str:
        return value if isinstance(value, str) else ""
