from PySide6.QtWidgets import QMainWindow, QSplitter, QWidget, QVBoxLayout, QToolBar, QFileDialog, QDoubleSpinBox, QCheckBox, QComboBox
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt
from .browser_widget import BrowserWidget
from .editor_widget import EditorWidget
from .canvas_widget import CanvasWidget

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Texture Atlas Editor")
        self.resize(1280, 720)

        # Toolbar
        self.toolbar = QToolBar("Main Toolbar")
        self.addToolBar(self.toolbar)

        open_folder_action = QAction("Open Folder", self)
        open_folder_action.triggered.connect(self.open_folder)
        self.toolbar.addAction(open_folder_action)

        self.toolbar.addSeparator()
        
        self.density_input = QDoubleSpinBox()
        self.density_input.setRange(1.0, 4096.0)
        self.density_input.setValue(512.0)
        self.density_input.setPrefix("Atlas Density: ")
        self.density_input.setSuffix(" px/m")
        self.density_input.valueChanged.connect(self.on_density_changed)
        self.toolbar.addWidget(self.density_input)
        
        self.grid_chk = QCheckBox("Show Grid")
        self.grid_chk.stateChanged.connect(self.on_grid_toggled)
        self.toolbar.addWidget(self.grid_chk)
        
        self.size_combo = QComboBox()
        self.size_combo.addItems(["1024", "2048", "3072", "4096"])
        self.size_combo.setCurrentText("2048")
        self.size_combo.currentTextChanged.connect(self.on_size_changed)
        self.toolbar.addWidget(self.size_combo)

        self.toolbar.addSeparator()
        
        save_action = QAction("Save Project", self)
        save_action.triggered.connect(self.save_project)
        self.toolbar.addAction(save_action)
        
        load_action = QAction("Load Project", self)
        load_action.triggered.connect(self.load_project)
        self.toolbar.addAction(load_action)
        
        export_action = QAction("Export PNG", self)
        export_action.triggered.connect(self.export_atlas)
        self.toolbar.addAction(export_action)

        # Main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Splitter
        splitter = QSplitter(Qt.Horizontal)
        
        # Widgets
        self.browser = BrowserWidget()
        self.editor = EditorWidget()
        self.canvas = CanvasWidget()

        splitter.addWidget(self.browser)
        splitter.addWidget(self.editor)
        splitter.addWidget(self.canvas)

        # Set initial sizes (approx 20%, 40%, 40%)
        splitter.setSizes([250, 500, 500])

        main_layout.addWidget(splitter)

        # Connections
        self.browser.image_selected.connect(self.on_image_selected)
        self.editor.mask_applied.connect(self.on_mask_applied)
        self.canvas.item_edit_requested.connect(self.on_item_edit_requested)
        
        # Data
        self.project_data = {'textures': {}, 'items': []}

    def open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Image Folder")
        if folder:
            self.browser.load_images(folder)

    def on_density_changed(self, value):
        self.canvas.set_atlas_density(value)
        
    def on_size_changed(self, text):
        size = int(text)
        self.canvas.set_canvas_size(size)
        self.project_data['atlas_size'] = size

    def on_grid_toggled(self, state):
        self.canvas.set_grid_visible(state == Qt.Checked)

    def on_image_selected(self, filepath):
        print(f"Selected: {filepath}")
        data = self.project_data['textures'].get(filepath, {})
        points = data.get('points')
        width = data.get('real_width')
        self.editor.load_image(filepath, points, width) # Clears editing_item
        
    def on_item_edit_requested(self, item):
        # Load item into editor
        self.editor.load_image(item.filepath, item.points, item.real_width, item)
        
    def on_mask_applied(self, filepath, points, real_width, original_width, item_ref):
        # Update data
        self.project_data['textures'][filepath] = {
            'points': points,
            'real_width': real_width,
            'original_width': original_width
        }
        
        if item_ref:
            # Update existing item
            self.canvas.update_item(item_ref, points, real_width, original_width)
        else:
            # Add new item
            self.canvas.add_fragment(filepath, points, real_width, original_width)

    def save_project(self):
        filepath, _ = QFileDialog.getSaveFileName(self, "Save Project", "", "JSON Files (*.json)")
        if filepath:
            import json
            self.project_data['base_path'] = self.browser.current_folder
            with open(filepath, 'w') as f:
                json.dump(self.project_data, f, indent=4)

    def load_project(self, filepath=None):
        if not filepath:
            filepath, _ = QFileDialog.getOpenFileName(self, "Load Project", "", "JSON Files (*.json)")
        
        if filepath:
            import json
            import os
            with open(filepath, 'r') as f:
                self.project_data = json.load(f)
            
            base_path = self.project_data.get('base_path')
            if base_path and os.path.exists(base_path):
                self.browser.load_images(base_path)
            
            # Restore settings
            self.density_input.setValue(self.project_data.get('atlas_density', 512.0))
            
            atlas_size = self.project_data.get('atlas_size', 2048)
            self.size_combo.setCurrentText(str(atlas_size))
            self.canvas.set_canvas_size(atlas_size)

            # Restore canvas
            self.canvas.scene.clear()
            for filepath, data in self.project_data.get('textures', {}).items():
                points = data.get('points')
                real_width = data.get('real_width')
                original_width = data.get('original_width')
                if points:
                    self.canvas.add_fragment(filepath, points, real_width, original_width)

    def export_atlas(self):
        filepath, _ = QFileDialog.getSaveFileName(self, "Export Atlas", "", "PNG Files (*.png)")
        if filepath:
            self.canvas.export_atlas(filepath)
