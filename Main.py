import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from GUI import RemReaderWindow


def main():

    # Create Qt application
    app = QApplication(
        sys.argv
    )

    # -------------------------
    # Application icon
    # -------------------------

    icon_path = (
        Path(__file__).parent
        / "assets"
        / "RemReader.ico"
    )

    app.setWindowIcon(
        QIcon(
            str(icon_path)
        )
    )

    # -------------------------
    # Create main window
    # -------------------------

    window = RemReaderWindow()

    window.show()

    # Start GUI event loop
    sys.exit(
        app.exec()
    )


if __name__ == "__main__":
    main()