from PySide6.QtWidgets import QMainWindow, QSplitter, QWidget, QVBoxLayout, QToolBar, QFileDialog, QDoubleSpinBox, QCheckBox, QComboBox
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QRadioButton, QSpinBox, QDialogButtonBox, QFormLayout, QDoubleSpinBox as QDoubleSpinBoxWidget, QProgressDialog, QApplication
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
        self.density_input.setKeyboardTracking(False) # Apply on Enter/finish editing
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

        resample_action = QAction("Resample Settings", self)
        resample_action.triggered.connect(self.open_resample_settings)
        self.toolbar.addAction(resample_action)

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
        self.project_data = {
            'textures': {},
            'items': [],
            'resample_mode': 'lanczos',
            'kaiser_beta': 3.0,
            'kaiser_radius': 2,
            'atlas_density': 512.0,
            'atlas_size': 2048
        }

    def open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Image Folder")
        if folder:
            self.browser.load_images(folder)

    def on_density_changed(self, value):
        self.project_data['atlas_density'] = value
        self.canvas.set_atlas_density(value, show_progress=True)
        
    def on_size_changed(self, text):
        size = int(text)
        self.canvas.set_canvas_size(size)
        self.project_data['atlas_size'] = size

    def on_grid_toggled(self, state):
        checked = Qt.CheckState(state) == Qt.CheckState.Checked
        self.canvas.set_grid_visible(checked)

    def on_image_selected(self, filepath):
        print(f"Selected: {filepath}")
        data = self.project_data['textures'].get(filepath, {})
        points = data.get('points')
        width = data.get('real_width')
        px_per_meter = data.get('px_per_meter')
        self.editor.load_image(filepath, points, width, px_per_meter=px_per_meter) # Clears editing_item
        
    def on_item_edit_requested(self, item):
        # Load item into editor
        data = self.project_data['textures'].get(item.filepath, {})
        px_per_meter = data.get('px_per_meter')
        self.editor.load_image(item.filepath, item.points, item.real_width, item, px_per_meter)
        
    def on_mask_applied(self, filepath, points, real_width, original_width, item_ref):
        # Update data
        self.project_data['textures'][filepath] = {
            'points': points,
            'real_width': real_width,
            'original_width': original_width,
            'px_per_meter': self.editor.px_per_meter
        }
        
        if item_ref:
            # Update existing item
            self.canvas.update_item(item_ref, points, real_width, original_width, show_progress=True)
        else:
            # Add new item
            self.canvas.add_fragment(filepath, points, real_width, original_width, show_progress=True)

    def save_project(self):
        filepath, _ = QFileDialog.getSaveFileName(self, "Save Project", "", "JSON Files (*.json)")
        if filepath:
            import json
            self.project_data['base_path'] = self.browser.current_folder
            self.project_data['atlas_density'] = self.density_input.value()
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

            # Resample settings
            mode = self.project_data.get('resample_mode', 'lanczos')
            beta = self.project_data.get('kaiser_beta', 3.0)
            radius = self.project_data.get('kaiser_radius', 2)
            self.canvas.set_resample_settings(mode, beta, radius)
            # Ensure density applied (valueChanged will fire, but be explicit)
            self.canvas.set_atlas_density(self.density_input.value(), show_progress=False)

            # Restore canvas
            self.canvas.scene.clear()
            tex_items = list(self.project_data.get('textures', {}).items())
            use_progress = len(tex_items) > 0
            dlg = None
            if use_progress:
                dlg = QProgressDialog("Resampling textures...", None, 0, len(tex_items), self)
                dlg.setWindowModality(Qt.ApplicationModal)
                dlg.setMinimumDuration(0)
                dlg.show()
            for idx, (filepath, data) in enumerate(tex_items, start=1):
                points = data.get('points')
                real_width = data.get('real_width')
                original_width = data.get('original_width')
                if points:
                    self.canvas.add_fragment(filepath, points, real_width, original_width, show_progress=True)
                if dlg:
                    dlg.setValue(idx)
                    QApplication.processEvents()
                    if dlg.wasCanceled():
                        break
            if dlg:
                dlg.close()

    def export_atlas(self):
        filepath, _ = QFileDialog.getSaveFileName(self, "Export Atlas", "", "PNG Files (*.png)")
        if filepath:
            self.canvas.export_atlas(filepath)

    def open_resample_settings(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Resample Settings")
        layout = QVBoxLayout(dialog)

        lanczos_radio = QRadioButton("Lanczos (default)")
        kaiser_radio = QRadioButton("Kaiser")
        if self.project_data.get('resample_mode', 'lanczos') == 'kaiser':
            kaiser_radio.setChecked(True)
        else:
            lanczos_radio.setChecked(True)

        layout.addWidget(lanczos_radio)
        layout.addWidget(kaiser_radio)

        form = QFormLayout()
        beta_spin = QDoubleSpinBoxWidget()
        beta_spin.setRange(0.1, 20.0)
        beta_spin.setValue(self.project_data.get('kaiser_beta', 3.0))
        beta_spin.setSingleStep(0.1)
        form.addRow("Kaiser beta", beta_spin)

        radius_spin = QSpinBox()
        radius_spin.setRange(1, 8)
        radius_spin.setValue(int(self.project_data.get('kaiser_radius', 2)))
        form.addRow("Kaiser radius", radius_spin)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)

        def accept():
            mode = 'kaiser' if kaiser_radio.isChecked() else 'lanczos'
            beta = beta_spin.value()
            radius = radius_spin.value()
            self.project_data['resample_mode'] = mode
            self.project_data['kaiser_beta'] = beta
            self.project_data['kaiser_radius'] = radius
            self.canvas.set_resample_settings(mode, beta, radius)
            dialog.accept()

        buttons.accepted.connect(accept)
        buttons.rejected.connect(dialog.reject)

        dialog.exec()
