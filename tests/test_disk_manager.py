import json
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

    def test_ext4_fstab_line_uses_pass_2(self) -> None:
        line = self._fstab_line_for("ext4", "ext4-uuid")

        self.assertEqual(
            "UUID=ext4-uuid /games/Games ext4 "
            "defaults,nofail,x-systemd.device-timeout=5 0 2",
            line,
        )

    def test_ntfs_fstab_line_uses_pass_0(self) -> None:
        line = self._fstab_line_for("ntfs", "ntfs-uuid")

        self.assertEqual(
            "UUID=ntfs-uuid /games/Games ntfs "
            "defaults,nofail,x-systemd.device-timeout=5 0 0",
            line,
        )

    def test_ntfs3_fstab_line_uses_pass_0(self) -> None:
        line = self._fstab_line_for("ntfs3", "ntfs3-uuid")

        self.assertEqual(
            "UUID=ntfs3-uuid /games/Games ntfs3 "
            "defaults,nofail,x-systemd.device-timeout=5 0 0",
            line,
        )

    def test_exfat_fstab_line_uses_pass_0(self) -> None:
        line = self._fstab_line_for("exfat", "exfat-uuid")

        self.assertEqual(
            "UUID=exfat-uuid /games/Games exfat "
            "defaults,nofail,x-systemd.device-timeout=5 0 0",
            line,
        )

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

    def _fstab_line_for(self, filesystem: str, uuid: str) -> str:
        partition = DiskPartition(
            device="/dev/sdb1",
            size="1G",
            filesystem=filesystem,
            label="Games",
            uuid=uuid,
            mountpoint="",
            has_steamapps=False,
        )
        return DiskManager().create_mount_plan(partition).fstab_line


if __name__ == "__main__":
    unittest.main()
