from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from bc250_manager.modules.dashboard import DashboardPage
from bc250_manager.modules.disks import DisksPage
from bc250_manager.modules.emudeck import EmuDeckPage
from bc250_manager.modules.settings import SettingsPage
from bc250_manager.modules.steam import SteamPage


@dataclass(frozen=True)
class NavigationItem:
    title: str
    widget: QWidget


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("BC250 Manager")
        self.resize(1180, 760)

        self._navigation = QListWidget()
        self._stack = QStackedWidget()

        self._configure_window()
        self._register_pages()
        self._apply_styles()

    def _configure_window(self) -> None:
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        sidebar = self._build_sidebar()
        root_layout.addWidget(sidebar)
        root_layout.addWidget(self._stack, stretch=1)

        self.setCentralWidget(root)

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(236)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(18, 20, 18, 20)
        layout.setSpacing(18)

        title = QLabel("BC250 Manager")
        title.setObjectName("AppTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)

        subtitle = QLabel("Control center")
        subtitle.setObjectName("AppSubtitle")

        header = QWidget()
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(4)
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)

        self._navigation.setObjectName("Navigation")
        self._navigation.setFrameShape(QFrame.Shape.NoFrame)
        self._navigation.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._navigation.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._navigation.currentRowChanged.connect(self._stack.setCurrentIndex)

        layout.addWidget(header)
        layout.addWidget(self._navigation)

        return sidebar

    def _register_pages(self) -> None:
        pages = [
            NavigationItem("Dashboard", DashboardPage()),
            NavigationItem("Disks", DisksPage()),
            NavigationItem("Steam", SteamPage()),
            NavigationItem("EmuDeck", EmuDeckPage()),
            NavigationItem("Settings", SettingsPage()),
        ]

        for page in pages:
            item = QListWidgetItem(page.title)
            item.setData(Qt.ItemDataRole.UserRole, page.title)
            self._navigation.addItem(item)
            self._stack.addWidget(page.widget)

        self._navigation.setCurrentRow(0)

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background: #f4f6f8;
            }

            #Sidebar {
                background: #17202a;
                border-right: 1px solid #0e141b;
            }

            #AppTitle {
                color: #ffffff;
                font-size: 20px;
                font-weight: 700;
            }

            #AppSubtitle {
                color: #93a4b7;
                font-size: 12px;
            }

            #Navigation {
                background: transparent;
                color: #d8e0ea;
                font-size: 14px;
                outline: none;
            }

            #Navigation::item {
                border-radius: 6px;
                padding: 10px 12px;
                margin: 3px 0;
            }

            #Navigation::item:selected {
                background: #2f80ed;
                color: #ffffff;
            }

            #Navigation::item:hover:!selected {
                background: #223040;
            }
            """
        )
