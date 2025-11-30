from PySide6.QtWidgets import QMainWindow, QSplitter, QWidget, QVBoxLayout, QToolBar, QFileDialog, QDoubleSpinBox, QCheckBox, QComboBox, QSizePolicy
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QRadioButton, QSpinBox, QDialogButtonBox, QFormLayout, QDoubleSpinBox as QDoubleSpinBoxWidget, QProgressDialog, QApplication
from .browser_widget import BrowserWidget
from .editor_widget import EditorWidget
from .canvas_widget import CanvasWidget, AtlasItem

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
        # Size policies
        self.browser.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.editor.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        splitter.addWidget(self.browser)
        splitter.addWidget(self.editor)
        splitter.addWidget(self.canvas)

        # Set initial sizes (approx 20%, 40%, 40%)
        splitter.setSizes([250, 500, 500])
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 3)

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
        data = self.project_data['textures'].setdefault(filepath, {'px_per_meter': None, 'masks': []})
        px_per_meter = data.get('px_per_meter')
        # For new mask creation, start blank but keep scale info if available
        self.editor.load_image(filepath, None, None, px_per_meter=px_per_meter) # Clears editing_item
        
    def on_item_edit_requested(self, item):
        # Load item into editor
        data = self.project_data['textures'].setdefault(item.filepath, {'px_per_meter': None, 'masks': []})
        px_per_meter = data.get('px_per_meter')
        mask_entry = None
        for m in data.get('masks', []):
            if m.get('id') == getattr(item, 'mask_id', None):
                mask_entry = m
                break
        points = mask_entry.get('points') if mask_entry else item.points
        real_width = mask_entry.get('real_width') if mask_entry else item.real_width
        original_width = mask_entry.get('original_width') if mask_entry else item.original_width
        self.editor.load_image(item.filepath, points, real_width, item, px_per_meter, getattr(item, 'mask_id', None))
        
    def on_mask_applied(self, filepath, points, real_width, original_width, item_ref, mask_id):
        # Ensure texture entry
        tex_entry = self.project_data['textures'].setdefault(filepath, {
            'px_per_meter': self.editor.px_per_meter,
            'masks': []
        })
        if self.editor.px_per_meter:
            tex_entry['px_per_meter'] = self.editor.px_per_meter

        if mask_id is None:
            if item_ref:
                mask_id = getattr(item_ref, 'mask_id', None)
            else:
                mask_id = self.editor.current_mask_id

        # Update existing mask or create new
        existing = None
        for m in tex_entry['masks']:
            if m.get('id') == mask_id:
                existing = m
                break

        if existing:
            existing['points'] = points
            existing['real_width'] = real_width
            existing['original_width'] = original_width
        else:
            # Assign new id
            next_id = max([m.get('id', 0) for m in tex_entry['masks']] + [0]) + 1
            mask_id = next_id
            tex_entry['masks'].append({
                'id': mask_id,
                'points': points,
                'real_width': real_width,
                'original_width': original_width
            })

        if item_ref:
            item_ref.mask_id = mask_id
            self.canvas.update_item(item_ref, points, real_width, original_width, mask_id=mask_id, show_progress=True)
        else:
            # Add new item
            self.canvas.add_fragment(filepath, points, real_width, original_width, mask_id=mask_id, show_progress=True)

    def save_project(self):
        filepath, _ = QFileDialog.getSaveFileName(self, "Save Project", "", "JSON Files (*.json)")
        if filepath:
            import json
            self.project_data['base_path'] = self.browser.current_folder
            self.project_data['atlas_density'] = self.density_input.value()
            # Capture item positions
            items_data = []
            for it in self.canvas.scene.items():
                if isinstance(it, AtlasItem):
                    items_data.append({
                        'filepath': it.filepath,
                        'mask_id': getattr(it, 'mask_id', None),
                        'x': it.pos().x(),
                        'y': it.pos().y()
                    })
            self.project_data['items'] = items_data
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

            # Normalize legacy texture data to new masks list
            textures = self.project_data.get('textures', {})
            for tex_path, data in list(textures.items()):
                if 'masks' not in data:
                    textures[tex_path] = {
                        'px_per_meter': data.get('px_per_meter'),
                        'masks': [{
                            'id': 1,
                            'points': data.get('points'),
                            'real_width': data.get('real_width'),
                            'original_width': data.get('original_width')
                        }]
                    }
            
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
            item_map = {}
            for idx, (filepath, data) in enumerate(tex_items, start=1):
                masks = data.get('masks')
                if masks:
                    for m in masks:
                        points = m.get('points')
                        real_width = m.get('real_width')
                        original_width = m.get('original_width')
                        mask_id = m.get('id')
                        if points:
                            item = self.canvas.add_fragment(filepath, points, real_width, original_width, mask_id=mask_id, show_progress=True)
                            if item:
                                item_map[(filepath, mask_id)] = item
                else:
                    # Legacy single mask structure
                    points = data.get('points')
                    real_width = data.get('real_width')
                    original_width = data.get('original_width')
                    if points:
                        item = self.canvas.add_fragment(filepath, points, real_width, original_width, mask_id=1, show_progress=True)
                        if item:
                            item_map[(filepath, 1)] = item
                if dlg:
                    dlg.setValue(idx)
                    QApplication.processEvents()
                    if dlg.wasCanceled():
                        break
            if dlg:
                dlg.close()

            # Restore positions
            for entry in self.project_data.get('items', []):
                key = (entry.get('filepath'), entry.get('mask_id'))
                item = item_map.get(key)
                if item:
                    item.setPos(entry.get('x', 0), entry.get('y', 0))

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
