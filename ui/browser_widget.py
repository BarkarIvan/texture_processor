import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QLabel, QSizePolicy
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtCore import Signal, QSize, Qt

class BrowserWidget(QWidget):
    image_selected = Signal(str) # Emits filepath

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.setMinimumWidth(180)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        
        self.header_label = QLabel("No folder selected")
        layout.addWidget(self.header_label)

        self.list_widget = QListWidget()
        self.list_widget.setIconSize(QSize(64, 64))
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        layout.addWidget(self.list_widget)
        
        self.current_folder = None

    def load_images(self, folder_path):
        self.current_folder = folder_path
        self.list_widget.clear()
        self.header_label.setText(f"Folder: {folder_path}")
        
        valid_extensions = {'.png', '.jpg', '.jpeg', '.tga', '.bmp'}
        
        try:
            for filename in os.listdir(folder_path):
                ext = os.path.splitext(filename)[1].lower()
                if ext in valid_extensions:
                    filepath = os.path.join(folder_path, filename)
                    
                    # Create item
                    item = QListWidgetItem(filename)
                    item.setData(Qt.UserRole, filepath)
                    
                    # Load thumbnail (basic)
                    pixmap = QPixmap(filepath)
                    if not pixmap.isNull():
                        icon = QIcon(pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                        item.setIcon(icon)
                        item.setToolTip(f"{filename}\n{pixmap.width()}x{pixmap.height()}")
                    
                    self.list_widget.addItem(item)
        except Exception as e:
            self.header_label.setText(f"Error: {e}")

    def on_item_clicked(self, item):
        filepath = item.data(Qt.UserRole)
        self.image_selected.emit(filepath)
