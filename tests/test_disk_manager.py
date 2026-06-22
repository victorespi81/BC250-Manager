import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bc250_manager.services.disk_manager import DiskDetectionError, DiskManager


class DiskManagerTests(unittest.TestCase):
    def test_filters_ignored_and_unsupported_partitions(self) -> None:
        payload = {
            "blockdevices": [
                {
                    "name": "sda",
                    "type": "disk",
                    "children": [
                        self._partition("sda1", "ext4", "/"),
                        self._partition("sda2", "ext4", "/boot"),
                        self._partition("sda3", "vfat", "/boot/efi", label="EFI"),
                        self._partition("sda4", "swap", ""),
                        self._partition("sda5", "crypto_LUKS", ""),
                        self._partition("sda6", "btrfs", "/mnt/games"),
                    ],
                }
            ]
        }

        partitions = DiskManager().parse_lsblk_output(json.dumps(payload))

        self.assertEqual(1, len(partitions))
        self.assertEqual("/dev/sda6", partitions[0].device)
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

    def _partition(
        self,
        name: str,
        filesystem: str,
        mountpoint: str,
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
            "mountpoints": [mountpoint] if mountpoint else [],
            "type": "part",
        }


if __name__ == "__main__":
    unittest.main()
