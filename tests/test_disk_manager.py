import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bc250_manager.services.disk_manager import DiskDetectionError, DiskManager, DiskPartition


class DiskManagerTests(unittest.TestCase):
    def test_filters_ignored_and_unsupported_partitions(self) -> None:
        payload = {
            "blockdevices": [
                {
                    "name": "sda",
                    "path": "/dev/sda",
                    "type": "disk",
                    "children": [
                        self._partition("sda1", "ext4", "/"),
                        self._partition("sda2", "ext4", "/boot"),
                        self._partition("sda3", "vfat", "/boot/efi", label="EFI"),
                        self._partition("sda4", "swap", ""),
                        self._partition("sda5", "crypto_LUKS", ""),
                        self._partition("sda6", "ext4", "/mnt/no-uuid"),
                    ],
                },
                {
                    "name": "sdb",
                    "path": "/dev/sdb",
                    "type": "disk",
                    "children": [
                        self._partition("sdb1", "btrfs", "/mnt/games", uuid="games-uuid"),
                    ],
                }
            ]
        }

        partitions = DiskManager().parse_lsblk_output(json.dumps(payload))

        self.assertEqual(1, len(partitions))
        self.assertEqual("/dev/sdb1", partitions[0].device)
        self.assertEqual("btrfs", partitions[0].filesystem)

    def test_detects_steamapps_for_supported_mountpoint(self) -> None:
        with tempfile.TemporaryDirectory() as mountpoint:
            Path(mountpoint, "steamapps").mkdir()
            payload = {
                "blockdevices": [
                    {
                        "name": "nvme0n1",
                        "type": "disk",
                        "children": [
                            self._partition(
                                "nvme0n1p1",
                                "ntfs3",
                                mountpoint,
                                label="Games",
                                uuid="abc-123",
                            )
                        ],
                    }
                ]
            }

            partitions = DiskManager().parse_lsblk_output(json.dumps(payload))

        self.assertEqual(1, len(partitions))
        self.assertEqual("Games", partitions[0].label)
        self.assertEqual("abc-123", partitions[0].uuid)
        self.assertTrue(partitions[0].has_steamapps)

    def test_rejects_invalid_lsblk_json(self) -> None:
        with self.assertRaises(DiskDetectionError):
            DiskManager().parse_lsblk_output("not-json")

    def test_system_btrfs_with_multiple_mountpoints_is_hidden(self) -> None:
        payload = {
            "blockdevices": [
                {
                    "name": "nvme0n1",
                    "path": "/dev/nvme0n1",
                    "type": "disk",
                    "children": [
                        self._partition(
                            "nvme0n1p2",
                            "btrfs",
                            ["/", "/home", "/var", "/root", "/srv", "/run"],
                            label="CACHYOS",
                            uuid="system-uuid",
                        )
                    ],
                }
            ]
        }

        partitions = DiskManager().parse_lsblk_output(json.dumps(payload))

        self.assertEqual([], partitions)

    def test_efi_vfat_is_hidden(self) -> None:
        payload = {
            "blockdevices": [
                {
                    "name": "sda",
                    "type": "disk",
                    "children": [
                        self._partition("sda1", "vfat", "/efi", label="EFI", uuid="efi-uuid")
                    ],
                }
            ]
        }

        partitions = DiskManager().parse_lsblk_output(json.dumps(payload))

        self.assertEqual([], partitions)

    def test_iso9660_installer_media_is_hidden(self) -> None:
        payload = {
            "blockdevices": [
                {
                    "name": "sda",
                    "type": "disk",
                    "children": [
                        self._partition(
                            "sda1",
                            "iso9660",
                            "/run/media/cachyos/ISO",
                            uuid="iso-uuid",
                        )
                    ],
                }
            ]
        }

        partitions = DiskManager().parse_lsblk_output(json.dumps(payload))

        self.assertEqual([], partitions)

    def test_ext4_mounted_at_games_is_shown(self) -> None:
        payload = {
            "blockdevices": [
                {
                    "name": "nvme0n1",
                    "path": "/dev/nvme0n1",
                    "type": "disk",
                    "children": [
                        self._partition(
                            "nvme0n1p2",
                            "btrfs",
                            ["/", "/home", "/var"],
                            label="CACHYOS",
                            uuid="system-uuid",
                        ),
                    ],
                },
                {
                    "name": "sdb",
                    "path": "/dev/sdb",
                    "type": "disk",
                    "children": [
                        self._partition(
                            "sdb1",
                            "ext4",
                            "/games/HDD_Juegos",
                            label="Games",
                            uuid="games-uuid",
                        )
                    ],
                },
            ]
        }

        partitions = DiskManager().parse_lsblk_output(json.dumps(payload))

        self.assertEqual(1, len(partitions))
        partition = partitions[0]
        self.assertEqual("/dev/sdb1", partition.device)
        self.assertEqual("/games/HDD_Juegos", partition.mountpoint)

    def test_ext4_unmounted_data_disk_is_shown(self) -> None:
        payload = {
            "blockdevices": [
                {
                    "name": "sdc",
                    "type": "disk",
                    "children": [
                        self._partition("sdc1", "ext4", "", label="Data", uuid="data-uuid")
                    ],
                }
            ]
        }

        partitions = DiskManager().parse_lsblk_output(json.dumps(payload))

        self.assertEqual(1, len(partitions))
        self.assertEqual("/dev/sdc1", partitions[0].device)
        self.assertEqual("", partitions[0].mountpoint)

    def test_ntfs_unmounted_data_disk_is_shown(self) -> None:
        payload = {
            "blockdevices": [
                {
                    "name": "sdd",
                    "type": "disk",
                    "children": [
                        self._partition("sdd1", "ntfs", "", label="WindowsGames", uuid="ntfs-uuid")
                    ],
                }
            ]
        }

        partitions = DiskManager().parse_lsblk_output(json.dumps(payload))

        self.assertEqual(1, len(partitions))
        self.assertEqual("/dev/sdd1", partitions[0].device)
        self.assertEqual("ntfs", partitions[0].filesystem)

    def test_mount_plan_uses_uuid_and_safe_games_mountpoint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fstab_path = Path(temp_dir) / "fstab"
            fstab_path.write_text("", encoding="utf-8")
            manager = DiskManager(fstab_path=fstab_path)

            plan = manager.create_mount_plan(
                self._disk_partition(label="My Games!", uuid="plan-uuid")
            )

        self.assertEqual("/games/My_Games", plan.target_mountpoint)
        self.assertEqual(
            "UUID=plan-uuid /games/My_Games ext4 "
            "defaults,nofail,x-systemd.device-timeout=5 0 2",
            plan.fstab_line,
        )
        self.assertFalse(plan.fstab_entry_exists)

    def test_ext4_fstab_line_uses_pass_2(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fstab_path = Path(temp_dir) / "fstab"
            fstab_path.write_text("", encoding="utf-8")
            manager = DiskManager(fstab_path=fstab_path)

            plan = manager.create_mount_plan(
                self._disk_partition(filesystem="ext4", uuid="ext4-uuid")
            )

        self.assertEqual(
            "UUID=ext4-uuid /games/Games ext4 "
            "defaults,nofail,x-systemd.device-timeout=5 0 2",
            plan.fstab_line,
        )

    def test_ntfs_fstab_line_uses_pass_0(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fstab_path = Path(temp_dir) / "fstab"
            fstab_path.write_text("", encoding="utf-8")
            manager = DiskManager(fstab_path=fstab_path)

            plan = manager.create_mount_plan(
                self._disk_partition(filesystem="ntfs", uuid="ntfs-plan-uuid")
            )

        self.assertEqual(
            "UUID=ntfs-plan-uuid /games/Games ntfs "
            "defaults,nofail,x-systemd.device-timeout=5 0 0",
            plan.fstab_line,
        )

    def test_ntfs3_fstab_line_uses_pass_0(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fstab_path = Path(temp_dir) / "fstab"
            fstab_path.write_text("", encoding="utf-8")
            manager = DiskManager(fstab_path=fstab_path)

            plan = manager.create_mount_plan(
                self._disk_partition(filesystem="ntfs3", uuid="ntfs3-plan-uuid")
            )

        self.assertEqual(
            "UUID=ntfs3-plan-uuid /games/Games ntfs3 "
            "defaults,nofail,x-systemd.device-timeout=5 0 0",
            plan.fstab_line,
        )

    def test_exfat_fstab_line_uses_pass_0(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fstab_path = Path(temp_dir) / "fstab"
            fstab_path.write_text("", encoding="utf-8")
            manager = DiskManager(fstab_path=fstab_path)

            plan = manager.create_mount_plan(
                self._disk_partition(filesystem="exfat", uuid="exfat-plan-uuid")
            )

        self.assertEqual(
            "UUID=exfat-plan-uuid /games/Games exfat "
            "defaults,nofail,x-systemd.device-timeout=5 0 0",
            plan.fstab_line,
        )

    def test_existing_uuid_plan_does_not_assume_games_mountpoint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fstab_path = Path(temp_dir) / "fstab"
            fstab_path.write_text(
                "UUID=existing /mnt/existing ext4 defaults 0 2\n",
                encoding="utf-8",
            )
            manager = DiskManager(fstab_path=fstab_path)

            plan = manager.create_mount_plan(self._disk_partition(uuid="existing"))

        self.assertTrue(plan.fstab_entry_exists)
        self.assertEqual("", plan.target_mountpoint)
        self.assertEqual("", plan.fstab_line)

    def test_mount_partition_uses_pkexec_backup_and_mount_a(self) -> None:
        commands: list[list[str]] = []

        def runner(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            commands.append(command)
            return subprocess.CompletedProcess(command, 0, "", "")

        with tempfile.TemporaryDirectory() as temp_dir:
            fstab_path = Path(temp_dir) / "fstab"
            fstab_path.write_text("", encoding="utf-8")
            manager = DiskManager(command_runner=runner, fstab_path=fstab_path)

            result = manager.mount_partition(self._disk_partition(uuid="mount-uuid"))

        self.assertTrue(result.success)
        self.assertIn(["pkexec", "mkdir", "-p", "/games/Games"], commands)
        self.assertTrue(any(command[:3] == ["pkexec", "cp", str(fstab_path)] for command in commands))
        self.assertTrue(any(command[:3] == ["pkexec", "sh", "-c"] for command in commands))
        self.assertIn(["pkexec", "systemctl", "daemon-reload"], commands)
        self.assertIn(["pkexec", "mount", "-a"], commands)

    def test_mount_partition_does_not_duplicate_existing_uuid(self) -> None:
        commands: list[list[str]] = []

        def runner(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            commands.append(command)
            return subprocess.CompletedProcess(command, 0, "", "")

        with tempfile.TemporaryDirectory() as temp_dir:
            fstab_path = Path(temp_dir) / "fstab"
            fstab_path.write_text("UUID=existing /games/Games ext4 defaults 0 2\n", encoding="utf-8")
            manager = DiskManager(command_runner=runner, fstab_path=fstab_path)

            result = manager.mount_partition(self._disk_partition(uuid="existing"))

        self.assertFalse(result.success)
        self.assertIn("already exists", result.message)
        self.assertEqual("", result.plan.target_mountpoint)
        self.assertFalse(any(command[:2] == ["pkexec", "cp"] for command in commands))
        self.assertFalse(any(command[:3] == ["pkexec", "sh", "-c"] for command in commands))
        self.assertEqual([], commands)

    def test_mount_failure_restores_backup_after_fstab_edit(self) -> None:
        commands: list[list[str]] = []

        def runner(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            commands.append(command)
            if command == ["pkexec", "mount", "-a"]:
                raise subprocess.CalledProcessError(1, command, stderr="mount failed")
            return subprocess.CompletedProcess(command, 0, "", "")

        with tempfile.TemporaryDirectory() as temp_dir:
            fstab_path = Path(temp_dir) / "fstab"
            fstab_path.write_text("", encoding="utf-8")
            manager = DiskManager(command_runner=runner, fstab_path=fstab_path)

            result = manager.mount_partition(self._disk_partition(uuid="restore-uuid"))

        self.assertFalse(result.success)
        self.assertEqual("mount failed", result.message)
        self.assertTrue(
            any(
                command[:2] == ["pkexec", "cp"]
                and ".backup.bc250-manager." in command[2]
                and command[3] == str(fstab_path)
                for command in commands
            )
        )
        self.assertIn(["pkexec", "systemctl", "daemon-reload"], commands)

    def test_already_mounted_games_disk_does_not_run_privileged_commands(self) -> None:
        commands: list[list[str]] = []

        def runner(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            commands.append(command)
            return subprocess.CompletedProcess(command, 0, "", "")

        with tempfile.TemporaryDirectory() as temp_dir:
            fstab_path = Path(temp_dir) / "fstab"
            fstab_path.write_text("", encoding="utf-8")
            manager = DiskManager(command_runner=runner, fstab_path=fstab_path)

            result = manager.mount_partition(
                self._disk_partition(mountpoint="/games/Games", uuid="mounted-uuid")
            )

        self.assertTrue(result.success)
        self.assertEqual([], commands)

    def _partition(
        self,
        name: str,
        filesystem: str,
        mountpoint: str | list[str],
        *,
        label: str = "",
        uuid: str = "",
    ) -> dict[str, object]:
        return {
            "name": name,
            "path": f"/dev/{name}",
            "size": "1G",
            "fstype": filesystem,
            "label": label,
            "uuid": uuid,
            "mountpoints": self._mountpoints(mountpoint),
            "type": "part",
        }

    def _mountpoints(self, mountpoint: str | list[str]) -> list[str]:
        if isinstance(mountpoint, list):
            return mountpoint

        return [mountpoint] if mountpoint else []

    def _disk_partition(
        self,
        *,
        device: str = "/dev/sdb1",
        filesystem: str = "ext4",
        label: str = "Games",
        uuid: str = "games-uuid",
        mountpoint: str = "",
    ) -> DiskPartition:
        return DiskPartition(
            device=device,
            size="1G",
            filesystem=filesystem,
            label=label,
            uuid=uuid,
            mountpoint=mountpoint,
            has_steamapps=False,
        )


if __name__ == "__main__":
    unittest.main()
