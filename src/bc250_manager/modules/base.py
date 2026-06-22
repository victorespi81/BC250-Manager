from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ModulePage(QWidget):
    def __init__(self, title: str, description: str) -> None:
        super().__init__()

        self.setObjectName("ModulePage")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(34, 30, 34, 30)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        heading = QLabel(title)
        heading.setObjectName("ModuleHeading")

        body = QLabel(description)
        body.setObjectName("ModuleDescription")
        body.setWordWrap(True)

        layout.addWidget(heading)
        layout.addWidget(body)
        layout.addStretch()

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
