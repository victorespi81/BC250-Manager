from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
)

from bc250_manager.modules.base import ModulePage
from bc250_manager.services.disk_manager import DiskDetectionError, DiskManager, DiskPartition, MountPlan


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
        self._partitions: list[DiskPartition] = []
        self._table = QTableWidget(0, len(self.COLUMNS))
        self._status = QLabel()
        self._refresh_button = QPushButton("Refresh")
        self._mount_button = QPushButton("Mount selected")

        self._configure_ui()
        self.refresh()

    def _configure_ui(self) -> None:
        self._refresh_button.setObjectName("RefreshButton")
        self._refresh_button.clicked.connect(self.refresh)

        self._mount_button.setObjectName("MountButton")
        self._mount_button.setEnabled(False)
        self._mount_button.clicked.connect(self._mount_selected)

        self._status.setObjectName("StatusText")
        self._status.setWordWrap(True)

        self._table.setObjectName("DisksTable")
        self._table.setHorizontalHeaderLabels(self.COLUMNS)
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.itemSelectionChanged.connect(self._update_mount_button)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)

        self.content_layout.addWidget(self._refresh_button, 0, Qt.AlignmentFlag.AlignRight)
        self.content_layout.addWidget(self._mount_button, 0, Qt.AlignmentFlag.AlignRight)
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

            #RefreshButton,
            #MountButton {
                background: #2f80ed;
                border: none;
                border-radius: 6px;
                color: #ffffff;
                font-size: 13px;
                font-weight: 600;
                padding: 8px 14px;
            }

            #RefreshButton:hover,
            #MountButton:hover {
                background: #256dca;
            }

            #MountButton:disabled {
                background: #aab7c4;
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
            self._partitions = []
            self._table.setRowCount(0)
            self._status.setText(f"Disk detection failed: {exc}")
        else:
            self._populate_table(partitions)
            count = len(partitions)
            self._status.setText(f"{count} supported partition{'s' if count != 1 else ''} found.")
        finally:
            self._refresh_button.setEnabled(True)

    def _populate_table(self, partitions: list[DiskPartition]) -> None:
        self._partitions = partitions
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

        self._update_mount_button()

    def _update_mount_button(self) -> None:
        self._mount_button.setEnabled(self._selected_partition() is not None)

    def _selected_partition(self) -> DiskPartition | None:
        selected_rows = self._table.selectionModel().selectedRows()
        if not selected_rows:
            return None

        row = selected_rows[0].row()
        if row < 0 or row >= len(self._partitions):
            return None

        return self._partitions[row]

    def _mount_selected(self) -> None:
        partition = self._selected_partition()
        if partition is None:
            return

        try:
            plan = self._disk_manager.create_mount_plan(partition)
        except DiskDetectionError as exc:
            QMessageBox.critical(self, "Mount failed", str(exc))
            return

        if not self._confirm_mount(plan):
            return

        try:
            self._disk_manager.mount_partition(partition)
        except DiskDetectionError as exc:
            QMessageBox.critical(self, "Mount failed", str(exc))
            return

        QMessageBox.information(self, "Mount complete", f"Mounted at {plan.target_mountpoint}.")
        self.refresh()

    def _confirm_mount(self, plan: MountPlan) -> bool:
        partition = plan.partition
        message = (
            f"Device: {partition.device}\n"
            f"Label: {partition.label or '-'}\n"
            f"Filesystem: {partition.filesystem}\n"
            f"UUID: {partition.uuid}\n"
            f"Target mountpoint: {plan.target_mountpoint}\n\n"
            f"fstab line:\n{plan.fstab_line}"
        )

        response = QMessageBox.question(
            self,
            "Confirm disk mount",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return response == QMessageBox.StandardButton.Yes
