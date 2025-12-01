import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont
from ui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    # Force a valid default point size to avoid Qt warnings
    app.setFont(QFont("Segoe UI", 9))
    window = MainWindow()
    window.show()
    print("Texture Atlas Editor started.")
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
