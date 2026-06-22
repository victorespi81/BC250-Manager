from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ModulePage(QWidget):
    def __init__(self, title: str, description: str) -> None:
        super().__init__()

        self.setObjectName("ModulePage")

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(34, 30, 34, 30)
        self._layout.setSpacing(10)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        heading = QLabel(title)
        heading.setObjectName("ModuleHeading")

        body = QLabel(description)
        body.setObjectName("ModuleDescription")
        body.setWordWrap(True)

        self._layout.addWidget(heading)
        self._layout.addWidget(body)

        self._content_layout = QVBoxLayout()
        self._content_layout.setContentsMargins(0, 8, 0, 0)
        self._content_layout.setSpacing(12)
        self._layout.addLayout(self._content_layout, stretch=1)

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
                line-height: 1.4;
            }
            """
        )

    @property
    def content_layout(self) -> QVBoxLayout:
        return self._content_layout
