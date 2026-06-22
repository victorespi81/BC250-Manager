import sys

from PySide6.QtWidgets import QApplication

from bc250_manager.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("BC250 Manager")
    app.setOrganizationName("BC250")

    window = MainWindow()
    window.show()

    return app.exec()
