from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
)

from bc250_manager.modules.base import ModulePage
from bc250_manager.services.disk_manager import DiskDetectionError, DiskManager, DiskPartition


class DisksPage(ModulePage):
    COLUMNS = (
        "Device",
        "Size",
        "Filesystem",
        "Label",
        "UUID",
        "Current mountpoint",
        "steamapps",
    )

    def __init__(self, disk_manager: DiskManager | None = None) -> None:
        super().__init__(
            title="Disks",
            description="Detected user-manageable partitions. This view does not mount disks or modify fstab.",
        )

        self._disk_manager = disk_manager or DiskManager()
        self._table = QTableWidget(0, len(self.COLUMNS))
        self._status = QLabel()
        self._refresh_button = QPushButton("Refresh")

        self._configure_ui()
        self.refresh()

    def _configure_ui(self) -> None:
        self._refresh_button.setObjectName("RefreshButton")
        self._refresh_button.clicked.connect(self.refresh)

        self._status.setObjectName("StatusText")
        self._status.setWordWrap(True)

        self._table.setObjectName("DisksTable")
        self._table.setHorizontalHeaderLabels(self.COLUMNS)
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)

        self.content_layout.addWidget(self._refresh_button, 0, Qt.AlignmentFlag.AlignRight)
        self.content_layout.addWidget(self._status)
        self.content_layout.addWidget(self._table, stretch=1)

        self.setStyleSheet(
            """
            #ModulePage {
                background: #f4f6f8;
            }

            #ModuleHeading {
                color: #17202a;
                font-size: 28px;
                font-weight: 700;
            }

            #ModuleDescription {
                color: #52616f;
                font-size: 14px;
            }

            #StatusText {
                color: #6b7785;
                font-size: 13px;
            }

            #RefreshButton {
                background: #2f80ed;
                border: none;
                border-radius: 6px;
                color: #ffffff;
                font-size: 13px;
                font-weight: 600;
                padding: 8px 14px;
            }

            #RefreshButton:hover {
                background: #256dca;
            }

            #DisksTable {
                background: #ffffff;
                alternate-background-color: #f8fafc;
                border: 1px solid #d9e0e8;
                border-radius: 6px;
                color: #17202a;
                gridline-color: #e3e8ef;
                selection-background-color: #dbeafe;
                selection-color: #17202a;
            }

            #DisksTable::item {
                padding: 6px;
            }

            QHeaderView::section {
                background: #eef2f6;
                border: none;
                border-bottom: 1px solid #d9e0e8;
                color: #384656;
                font-size: 12px;
                font-weight: 700;
                padding: 8px;
            }
            """
        )

    def refresh(self) -> None:
        self._refresh_button.setEnabled(False)
        self._status.setText("Refreshing disks...")

        try:
            partitions = self._disk_manager.list_partitions()
        except DiskDetectionError as exc:
            self._table.setRowCount(0)
            self._status.setText(f"Disk detection failed: {exc}")
        else:
            self._populate_table(partitions)
            count = len(partitions)
            self._status.setText(f"{count} supported partition{'s' if count != 1 else ''} found.")
        finally:
            self._refresh_button.setEnabled(True)

    def _populate_table(self, partitions: list[DiskPartition]) -> None:
        self._table.setRowCount(len(partitions))

        for row, partition in enumerate(partitions):
            values = (
                partition.device,
                partition.size,
                partition.filesystem,
                partition.label,
                partition.uuid,
                partition.mountpoint,
                "Yes" if partition.has_steamapps else "No",
            )

            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                self._table.setItem(row, column, item)
