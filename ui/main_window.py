import os
import re
import math
import gc
from collections import defaultdict
from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtCore import Qt

from core.workspace_manager import (
    MAX_VIEWS, create_empty_view_data, sort_files_for_mammo,
    scan_folder_for_files, distribute_files, determine_mode, get_projection_info
)
from core.utils import SUPPORTED_EXTS, DICOM_EXTS, IMAGE_EXTS, JSON_EXTS, PIL_AVAILABLE, convert_numpy_to_qimage
from core.image_loader import load_generic_file, apply_adjustments_pipeline, update_brightness_contrast_only
from core.image_processor import apply_brightness_contrast
from models.view_data import ViewData
from tools.tool_manager import ToolManager
from ui.viewport import InteractiveGraphicsView
from ui.sidebar import SidebarWidget
from ui.top_toolbar import TopToolbar
from ui.overlays import clear_overlay_items, update_image_overlay


class DICOMViewer(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Claude DICOM Viewer")
        self.resize(1300, 950)
        self.brightness = 0
        self.contrast = 1.0
        self.negative_mode = False
        self.focus_mode = False
        self.is_dark_theme = False

        self.app_config = {
            'dark_theme': False,
            'large_ui': False,
            'low_quality': False,
            'note_color': '#0000FF',
            'lang': 'ru'
        }

        self.view_data = [ViewData() for _ in range(MAX_VIEWS)]
        self.last_active_view_index = 0
        self.current_mode_index = 0
        self.all_scenes = []
        self.all_views = []

        self._setup_central_widget()
        self._create_view_widgets()
        self._setup_toolbar()
        self._setup_layout_for_mode(self.current_mode_index)
        self.setAcceptDrops(True)
        self._setup_shortcuts()

        QtCore.QTimer.singleShot(0, self._set_initial_focus_and_border)
        self._apply_theme()
        self.toolbar.update_toolbar_icons()

    def _setup_central_widget(self):
        self.central_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QtWidgets.QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Sidebar
        self.sidebar = SidebarWidget()
        self.sidebar.viewSwapToSidebar.connect(self._handle_main_view_to_sidebar_drop)
        self.main_layout.addWidget(self.sidebar, stretch=0)

        # Toggle handle (thin divider)
        self.toggle_handle = QtWidgets.QPushButton("◀")
        self.toggle_handle.setFixedWidth(18)
        self.toggle_handle.setObjectName("sidebarToggle")
        self.toggle_handle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_handle.clicked.connect(lambda: self.sidebar.toggle_visibility(self.toggle_handle))
        self.main_layout.addWidget(self.toggle_handle)

        # Viewport container (with padding around grid)
        self.viewport_container = QtWidgets.QWidget()
        viewport_layout = QtWidgets.QVBoxLayout(self.viewport_container)
        viewport_layout.setContentsMargins(12, 12, 12, 12)
        viewport_layout.setSpacing(0)

        self.stack = QtWidgets.QStackedWidget()
        viewport_layout.addWidget(self.stack)
        self.main_layout.addWidget(self.viewport_container, stretch=4)

    def _setup_toolbar(self):
        self.toolbar = TopToolbar(self)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbar)
        self.toolbar.build_toolbar()
        self.toolbar.modeChanged.connect(self._change_mode)
        self.toolbar.toolChanged.connect(self.set_tool_for_visible_views)
        self.toolbar.presetChanged.connect(self._apply_preset)
        self.toolbar.actionTriggered.connect(self._handle_toolbar_action)

    def _setup_shortcuts(self):
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Z"), self, self._undo_action)
        QtGui.QShortcut(QtGui.QKeySequence("F11"), self, self._toggle_focus)

    def _handle_toolbar_action(self, action_name):
        mapping = {
            "open_file": self.open_file_for_active_view,
            "open_folder": self.open_folder,
            "clear_active": self.clear_active_view_data,
            "clear_all": self.clear_all_views_data,
            "export": self.export_active_image,
            "info": self.show_study_info_dialog,
            "clear_drawings": self.clear_interactive_overlays,
            "zoom_in": self.zoom_in,
            "zoom_out": self.zoom_out,
            "reset_view": self.reset_view,
            "rotate": self.rotate_image,
            "flip_h": self.flip_horizontal,
            "flip_v": self.flip_vertical,
            "adjustments": self.open_adjustment_dialog,
            "undo": self._undo_action,
            "settings": self.open_settings,
            "help": self.open_help,
            "focus": self._toggle_focus,
            "toggle_theme": self.toggle_theme,
        }
        handler = mapping.get(action_name)
        if handler:
            handler()

    def _change_mode(self, index):
        if index != self.current_mode_index:
            self._setup_layout_for_mode(index)

    def _apply_preset(self, index):
        from core.utils import DICOM_PRESETS
        preset_name = self.toolbar.preset_combo.currentText()
        preset_val = DICOM_PRESETS.get(preset_name)
        idx = self.last_active_view_index
        if 0 <= idx < MAX_VIEWS:
            vd = self.view_data[idx]
            if not vd.is_loaded():
                return
            if preset_val:
                vd.wc, vd.ww = preset_val
            else:
                vd.wc, vd.ww = None, None
            apply_adjustments_pipeline(vd, self.brightness, self.contrast, self.negative_mode)
            self._update_single_view_display(idx)

    def _undo_action(self):
        if 0 <= self.last_active_view_index < MAX_VIEWS:
            self.all_views[self.last_active_view_index].undo_stack.undo()

    def _toggle_focus(self):
        self.focus_mode = not self.focus_mode
        self.sidebar.setVisible(not self.focus_mode)
        self.toolbar.setVisible(not self.focus_mode)

    def _set_initial_focus_and_border(self):
        if not self.all_views:
            return
        initial_view_index = self.last_active_view_index
        if not (0 <= initial_view_index < len(self.all_views)) or not self.all_views[initial_view_index].isVisible():
            visible_indices = [i for i, v in enumerate(self.all_views) if v.isVisible()]
            if visible_indices:
                initial_view_index = visible_indices[0]
            else:
                return
        initial_view = self.all_views[initial_view_index]
        initial_view.setFocus(Qt.FocusReason.OtherFocusReason)
        self._update_view_border(initial_view_index, True)
        for i, view in enumerate(self.all_views):
            if view.isVisible() and i != initial_view_index:
                self._update_view_border(i, False)

    def _create_view_widgets(self):
        self.view_container_widget = QtWidgets.QWidget()
        self.view_layout = QtWidgets.QGridLayout(self.view_container_widget)
        self.view_layout.setContentsMargins(0, 0, 0, 0)
        self.view_layout.setSpacing(10)
        for i in range(MAX_VIEWS):
            scene = QtWidgets.QGraphicsScene(self)
            view = InteractiveGraphicsView(scene, self)
            view.setObjectName(f"view_{i}")
            view.setMinimumSize(200, 200)
            view.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
            view.setBackgroundBrush(QtGui.QBrush(QtGui.QColor("#F0EEE6")))
            view.loadImageRequested.connect(self._handle_load_request)
            view.viewClicked.connect(self.set_active_view)
            view.folderOpenRequested.connect(self._handle_folder_open_request)
            view.viewDropOccurred.connect(self.swap_view_data)
            view.sidebarFileDropped.connect(self._handle_sidebar_drop)
            self.all_scenes.append(scene)
            self.all_views.append(view)
            view.setVisible(False)
        self.stack.addWidget(self.view_container_widget)

    def _setup_layout_for_mode(self, mode_index):
        self.current_mode_index = mode_index
        indices_to_show = []

        while self.view_layout.count():
            item = self.view_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setVisible(False)
                widget.setParent(None)

        if mode_index == 0:
            if not (0 <= self.last_active_view_index < MAX_VIEWS):
                self.last_active_view_index = 0
            idx = self.last_active_view_index
            indices_to_show = [idx]
            view = self.all_views[idx]
            self.view_layout.addWidget(view, 0, 0, 2, 2)
            view.setVisible(True)
        elif mode_index == 1:
            indices_to_show = list(range(min(2, MAX_VIEWS)))
            if len(indices_to_show) >= 1:
                v1 = self.all_views[indices_to_show[0]]
                self.view_layout.addWidget(v1, 0, 0, 2, 1)
                v1.setVisible(True)
            if len(indices_to_show) >= 2:
                v2 = self.all_views[indices_to_show[1]]
                self.view_layout.addWidget(v2, 0, 1, 2, 1)
                v2.setVisible(True)
            self.view_layout.setColumnStretch(0, 1)
            self.view_layout.setColumnStretch(1, 1)
            self.view_layout.setRowStretch(0, 1)
            self.view_layout.setRowStretch(1, 0)
        elif mode_index == 2:
            indices_to_show = list(range(min(4, MAX_VIEWS)))
            for i in indices_to_show:
                view = self.all_views[i]
                row, col = divmod(i, 2)
                self.view_layout.addWidget(view, row, col, 1, 1)
                view.setVisible(True)
            self.view_layout.setColumnStretch(0, 1)
            self.view_layout.setColumnStretch(1, 1)
            self.view_layout.setRowStretch(0, 1)
            self.view_layout.setRowStretch(1, 1)

        for i in range(MAX_VIEWS):
            if i not in indices_to_show:
                file_path = self.view_data[i].file_path
                if file_path and os.path.exists(file_path):
                    if file_path not in self.sidebar.extra_files:
                        self.sidebar.extra_files.append(file_path)
                    self._clear_view_data(i)
                self.all_views[i].setVisible(False)

        self.sidebar.update_sidebar()
        self._update_visible_views_display()
        if hasattr(self, 'toolbar') and self.toolbar.tool_group:
            self.set_tool_for_visible_views(self._get_current_tool())

        if 0 <= self.last_active_view_index < len(self.all_views) and self.all_views[self.last_active_view_index].isVisible():
            self._update_view_border(self.last_active_view_index, True)
            for i in indices_to_show:
                if i != self.last_active_view_index:
                    self._update_view_border(i, False)
            QtCore.QTimer.singleShot(0, lambda: self.all_views[self.last_active_view_index].setFocus(Qt.FocusReason.OtherFocusReason))
        elif indices_to_show:
            first_visible_idx = indices_to_show[0]
            self.last_active_view_index = first_visible_idx
            self._update_view_border(first_visible_idx, True)
            for i in indices_to_show:
                if i != first_visible_idx:
                    self._update_view_border(i, False)
            QtCore.QTimer.singleShot(0, lambda: self.all_views[first_visible_idx].setFocus(Qt.FocusReason.OtherFocusReason))

    def _get_visible_indices(self):
        if self.current_mode_index == 0:
            if not (0 <= self.last_active_view_index < MAX_VIEWS):
                self.last_active_view_index = 0
            return [self.last_active_view_index]
        elif self.current_mode_index == 1:
            return list(range(min(2, MAX_VIEWS)))
        elif self.current_mode_index == 2:
            return list(range(min(4, MAX_VIEWS)))
        return []

    def _get_current_views(self):
        return [v for v in self.all_views if v.isVisible()]

    def get_view_index(self, view_object):
        try:
            return self.all_views.index(view_object)
        except (ValueError, AttributeError):
            return -1

    def set_active_view(self, view_object):
        index = self.get_view_index(view_object)
        if index != -1:
            current_active = self.last_active_view_index
            if current_active != index:
                if 0 <= current_active < len(self.all_views):
                    self._update_view_border(current_active, False)
                self.last_active_view_index = index
            self._update_view_border(index, True)
            if self.current_mode_index == 0:
                self._setup_layout_for_mode(0)
            QtCore.QTimer.singleShot(0, lambda: view_object.setFocus(Qt.FocusReason.OtherFocusReason))

    def _update_view_border(self, index, active):
        if 0 <= index < len(self.all_views):
            view = self.all_views[index]
            if self.is_dark_theme:
                bg = "#1F1F1D"
                if active:
                    style = (f"QGraphicsView {{ border: 1.5px solid #D97757; border-radius: 10px;"
                             f"background-color: {bg}; }}")
                else:
                    style = (f"QGraphicsView {{ border: 1px solid rgba(250,249,245,0.08); border-radius: 10px;"
                             f"background-color: {bg}; }}")
                view.setBackgroundBrush(QtGui.QBrush(QtGui.QColor(bg)))
            else:
                bg = "#F0EEE6"
                if active:
                    style = (f"QGraphicsView {{ border: 1.5px solid #D97757; border-radius: 10px;"
                             f"background-color: {bg}; }}")
                else:
                    style = (f"QGraphicsView {{ border: 1px solid rgba(20,20,19,0.08); border-radius: 10px;"
                             f"background-color: {bg}; }}")
                view.setBackgroundBrush(QtGui.QBrush(QtGui.QColor(bg)))
            view.setStyleSheet(style)

    def _handle_load_request(self, view_object):
        index = self.get_view_index(view_object)
        if index != -1:
            self.set_active_view(view_object)
            self.open_file_for_view(index)

    def _handle_folder_open_request(self, view_object):
        view_index = self.get_view_index(view_object)
        if view_index == -1:
            return
        last_dir = os.path.dirname(self.view_data[view_index].file_path) if self.view_data[view_index].file_path else ""
        folder_path = QtWidgets.QFileDialog.getExistingDirectory(self, f"Выбрать папку для окна {view_index + 1}", last_dir)
        if folder_path:
            self.open_folder(start_path=folder_path)

    def _handle_sidebar_drop(self, target_idx, dropped_file_path):
        if dropped_file_path not in self.sidebar.extra_files:
            return
        file_currently_in_view = self.view_data[target_idx].file_path
        if file_currently_in_view and os.path.exists(file_currently_in_view):
            try:
                index_of_dropped_file = self.sidebar.extra_files.index(dropped_file_path)
                self.sidebar.extra_files[index_of_dropped_file] = file_currently_in_view
            except ValueError:
                self.sidebar.extra_files.remove(dropped_file_path)
                self.sidebar.extra_files.append(file_currently_in_view)
        else:
            self.sidebar.extra_files.remove(dropped_file_path)
        self._clear_view_data(target_idx)
        if self._load_generic_file(dropped_file_path, target_idx):
            self.set_active_view(self.all_views[target_idx])
            QtCore.QTimer.singleShot(50, lambda: self._update_image_overlay(target_idx))
        else:
            QtWidgets.QMessageBox.warning(self, "Ошибка", f"Не удалось загрузить файл: {dropped_file_path}")
            return
        self.sidebar.update_sidebar()

    def _handle_main_view_to_sidebar_drop(self, source_view_idx, source_file_path):
        if self.view_data[source_view_idx].file_path != source_file_path:
            return
        self.sidebar.extra_files.append(source_file_path)
        self._clear_view_data(source_view_idx)
        self._update_single_view_display(source_view_idx)
        self.sidebar.update_sidebar()

    def open_file_for_active_view(self):
        self.open_file_for_view(self.last_active_view_index)

    def open_file_for_view(self, view_index):
        if not (0 <= view_index < MAX_VIEWS):
            return
        last_dir = next((os.path.dirname(vd.file_path) for vd in reversed(self.view_data) if
                         vd.file_path and os.path.exists(os.path.dirname(vd.file_path))), "")
        filter_parts = []
        filter_parts.append("Все поддерживаемые (*" + " *".join(sorted(SUPPORTED_EXTS)) + ")")
        filter_parts.append("DICOM Files (*.dcm *.dicom *.ima *.img)")
        if PIL_AVAILABLE:
            filter_parts.append("Image Files (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)")
        filter_parts.append("JSON Files (*.json)")
        filter_parts.append("Все файлы (*)")
        file_name, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, f"Открыть файл для окна {view_index + 1}", last_dir, ";;".join(filter_parts))
        if file_name:
            self._clear_view_data(view_index)
            if self._load_generic_file(file_name, view_index):
                self.set_active_view(self.all_views[view_index])
            else:
                self._update_single_view_display(view_index)
            self.sidebar.extra_files.clear()
            self.sidebar.update_sidebar()

    def open_folder(self, start_path=None):
        if not start_path:
            last_dir = next((os.path.dirname(vd.file_path) for vd in reversed(self.view_data) if
                             vd.file_path and os.path.exists(os.path.dirname(vd.file_path))), "")
            options = QtWidgets.QFileDialog.Option.ShowDirsOnly
            folder_path = QtWidgets.QFileDialog.getExistingDirectory(self, "Выбрать папку", last_dir, options=options)
        else:
            folder_path = start_path
        if folder_path:
            all_files_in_folder = []
            files_by_ext = scan_folder_for_files(folder_path)
            for ext_list in files_by_ext.values():
                all_files_in_folder.extend(ext_list)
            if not all_files_in_folder:
                QtWidgets.QMessageBox.information(self, "Файлы не найдены",
                                                  f"В папке:\n{folder_path}\nне найдено поддерживаемых файлов.")
                return
            dicom_files = []
            for ext in DICOM_EXTS:
                if ext in files_by_ext:
                    dicom_files.extend(files_by_ext[ext])
            if dicom_files:
                self.load_files(all_files_in_folder)
            else:
                selected_files = self._show_format_selection_dialog(files_by_ext)
                if selected_files:
                    self.load_files(selected_files)

    def _show_format_selection_dialog(self, files_by_ext):
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Выбор формата файлов")
        dialog.setModal(True)
        dialog.resize(400, 300)
        layout = QtWidgets.QVBoxLayout(dialog)
        title_label = QtWidgets.QLabel("В папке не найдено приоритетных DICOM файлов.\nВыберите формат для загрузки:")
        title_label.setWordWrap(True)
        layout.addWidget(title_label)
        format_list = QtWidgets.QListWidget()
        format_list.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        format_groups = {'Изображения': IMAGE_EXTS, 'JSON': JSON_EXTS, 'DICOM (другие)': DICOM_EXTS}
        for group_name, exts in format_groups.items():
            group_files = []
            for ext in exts:
                if ext in files_by_ext:
                    group_files.extend(files_by_ext[ext])
            if group_files:
                item_text = f"{group_name} ({len(group_files)} файлов)"
                item = QtWidgets.QListWidgetItem(item_text)
                item.setData(Qt.ItemDataRole.UserRole, group_files)
                format_list.addItem(item)
        layout.addWidget(format_list)
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        button_box.button(QtWidgets.QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        format_list.itemSelectionChanged.connect(
            lambda: button_box.button(QtWidgets.QDialogButtonBox.StandardButton.Ok).setEnabled(True))
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            current_item = format_list.currentItem()
            if current_item:
                return current_item.data(Qt.ItemDataRole.UserRole)
        return None

    def load_files(self, file_paths):
        if not file_paths:
            return
        sorted_files = sort_files_for_mammo(file_paths)
        files_for_main, files_for_sidebar = distribute_files(sorted_files)
        self.clear_all_views_data()
        self.sidebar.extra_files = files_for_sidebar
        num_files = len(files_for_main)
        new_mode = determine_mode(num_files)
        if new_mode != self.current_mode_index:
            self.toolbar.set_current_mode(new_mode)
        else:
            self._setup_layout_for_mode(new_mode)
        QtCore.QTimer.singleShot(0, lambda: self._load_files_into_views(files_for_main))
        QtCore.QTimer.singleShot(0, self.sidebar.update_sidebar)

    def _load_files_into_views(self, files_to_load):
        loaded_count = 0
        first_loaded_index = -1
        for i, file_path in enumerate(files_to_load):
            if i >= MAX_VIEWS:
                break
            view_index = i
            if self._load_generic_file(file_path, view_index):
                loaded_count += 1
                if first_loaded_index == -1:
                    first_loaded_index = view_index
        if first_loaded_index != -1:
            self.set_active_view(self.all_views[first_loaded_index])
            self._update_visible_views_display()
        elif loaded_count == 0 and len(files_to_load) > 0:
            QtWidgets.QMessageBox.warning(self, "Ошибка загрузки", "Не удалось загрузить ни один из приоритетных файлов.")

    def _load_generic_file(self, file_path, view_index):
        if not (0 <= view_index < MAX_VIEWS):
            return False
        if not file_path or not os.path.exists(file_path):
            return False
        try:
            vd = load_generic_file(file_path)
            if vd is None:
                return False
            self.view_data[view_index] = vd
            apply_adjustments_pipeline(vd, self.brightness, self.contrast, self.negative_mode)
            self._update_single_view_display(view_index)
            return True
        except RuntimeError as e:
            QtWidgets.QMessageBox.critical(self, "Ошибка загрузки", str(e))
            self._clear_view_data(view_index)
            return False

    def _update_single_view_display(self, view_index):
        if not (0 <= view_index < MAX_VIEWS):
            return
        view = self.all_views[view_index]
        scene = self.all_scenes[view_index]
        vd = self.view_data[view_index]

        old_pixmap_item = vd.pixmap_item
        if old_pixmap_item and old_pixmap_item.scene() == scene:
            try:
                scene.removeItem(old_pixmap_item)
            except Exception:
                pass
        clear_overlay_items(scene, vd)
        view.set_image_data(None, 1.0, None)

        qimg = vd.qimage
        if qimg and not qimg.isNull():
            from PyQt6 import QtGui
            pixmap = QtGui.QPixmap.fromImage(qimg)
            if pixmap.isNull():
                scene.setSceneRect(QtCore.QRectF(0, 0, 1, 1))
                return
            new_pixmap_item = scene.addPixmap(pixmap)
            vd.pixmap_item = new_pixmap_item
            view.set_image_data(vd.adjusted_array, vd.pixel_spacing, new_pixmap_item)
            new_pixmap_item.setZValue(0)
            self._apply_item_transformations(view_index)
            scene_rect = new_pixmap_item.sceneBoundingRect()
            scene.setSceneRect(scene_rect)
            if view.isVisible():
                view.fitInView(scene_rect, Qt.AspectRatioMode.KeepAspectRatio)
                view.update_overlay_scaling()
                QtCore.QTimer.singleShot(10, lambda: self._update_image_overlay(view_index))
        else:
            scene.setSceneRect(QtCore.QRectF(0, 0, 1, 1))
            if view.isVisible():
                view.resetTransform()

    def _update_visible_views_display(self):
        for i, view in enumerate(self.all_views):
            if view.isVisible():
                self._update_single_view_display(i)

    def _update_image_overlay(self, view_index):
        if not (0 <= view_index < MAX_VIEWS):
            return
        vd = self.view_data[view_index]
        scene = self.all_scenes[view_index]
        view = self.all_views[view_index]
        update_image_overlay(view_index, vd, scene, view,
                             self.is_dark_theme, self.brightness, self.contrast, self.negative_mode)

    def _update_adjustments(self):
        for i in range(MAX_VIEWS):
            vd = self.view_data[i]
            if vd.base_8bit_array is not None:
                update_brightness_contrast_only(vd, self.brightness, self.contrast, self.negative_mode)
                if self.all_views[i]:
                    self.all_views[i].set_image_data(vd.adjusted_array, vd.pixel_spacing, vd.pixmap_item)
        self._update_visible_views_display()

    def _apply_item_transformations(self, view_index):
        vd = self.view_data[view_index]
        item = vd.pixmap_item
        if not item:
            return
        center = item.boundingRect().center()
        item.setTransformOriginPoint(center)
        transform = QtGui.QTransform()
        transform.translate(center.x(), center.y())
        transform.rotate(vd.rotation)
        transform.scale(-1 if vd.flip_h else 1, -1 if vd.flip_v else 1)
        transform.translate(-center.x(), -center.y())
        item.setTransform(transform)

    def _update_view_after_transform(self, view_index):
        view = self.all_views[view_index]
        item = self.view_data[view_index].pixmap_item
        if not item or not item.scene():
            return
        scene = item.scene()
        new_bounds = item.sceneBoundingRect()
        scene.setSceneRect(new_bounds)
        self._update_image_overlay(view_index)
        view.fitInView(new_bounds, Qt.AspectRatioMode.KeepAspectRatio)
        view.update_overlay_scaling()

    def swap_view_data(self, source_idx, target_idx):
        if not (0 <= source_idx < MAX_VIEWS and 0 <= target_idx < MAX_VIEWS):
            return
        if source_idx == target_idx:
            return
        self.all_views[source_idx].clear_all_drawing_items()
        self.all_views[target_idx].clear_all_drawing_items()
        self.view_data[source_idx], self.view_data[target_idx] = self.view_data[target_idx], self.view_data[source_idx]
        self._update_single_view_display(source_idx)
        self._update_single_view_display(target_idx)
        self.set_active_view(self.all_views[target_idx])

    def _clear_view_data(self, view_index):
        if not (0 <= view_index < MAX_VIEWS):
            return
        view = self.all_views[view_index]
        scene = self.all_scenes[view_index]
        view.clear_all_drawing_items()
        view.clear_image_data()
        if scene:
            all_scene_items = list(scene.items())
            for item in all_scene_items:
                try:
                    if item.scene() == scene:
                        scene.removeItem(item)
                except Exception:
                    pass
            scene.clear()
            scene.setSceneRect(QtCore.QRectF(0, 0, 1, 1))
        view.resetTransform()
        view.setDragMode(QtWidgets.QGraphicsView.DragMode.NoDrag)
        view.setCursor(Qt.CursorShape.ArrowCursor)
        view.image_array_ref = None
        view.pixel_spacing = 1.0
        view.pixmap_item_ref = None
        view._paired_view = None
        view.tool_mode = ToolManager.TOOL_NONE
        self.view_data[view_index] = ViewData()
        view.viewport().update()

    def clear_active_view_data(self):
        idx = self.last_active_view_index
        if 0 <= idx < MAX_VIEWS:
            self._clear_view_data(idx)
            self._update_single_view_display(idx)

    def clear_all_views_data(self):
        for i in range(MAX_VIEWS):
            self._clear_view_data(i)
        self.sidebar.extra_files.clear()
        self.sidebar.update_sidebar()
        self.brightness = 0
        self.contrast = 1.0
        self.negative_mode = False
        self.last_active_view_index = 0
        if hasattr(self.toolbar, 'tool_actions') and ToolManager.TOOL_NONE in self.toolbar.tool_actions:
            self.toolbar.tool_actions[ToolManager.TOOL_NONE].setChecked(True)
            self.set_tool_for_visible_views(ToolManager.TOOL_NONE)
        self._update_visible_views_display()
        QtCore.QTimer.singleShot(100, self._set_initial_focus_and_border)
        gc.collect()

    def clear_interactive_overlays(self):
        active_idx = self.last_active_view_index
        if 0 <= active_idx < MAX_VIEWS:
            self.all_views[active_idx].clear_all_drawing_items()

    def export_active_image(self):
        idx = self.last_active_view_index
        if not (0 <= idx < MAX_VIEWS):
            return
        vd = self.view_data[idx]
        scene = self.all_scenes[idx]
        if not vd.pixmap_item or vd.pixmap_item.pixmap().isNull():
            QtWidgets.QMessageBox.warning(self, "Экспорт", "Нет изображения для экспорта.")
            return
        src_rect = scene.itemsBoundingRect()
        if src_rect.isEmpty() or not src_rect.isValid():
            QtWidgets.QMessageBox.warning(self, "Экспорт", "Не удалось определить область для экспорта.")
            return
        src_rect.adjust(-10, -10, 10, 10)
        target_size = QtCore.QSize(math.ceil(src_rect.width()), math.ceil(src_rect.height()))
        img = QtGui.QImage(target_size, QtGui.QImage.Format.Format_ARGB32_Premultiplied)
        bg_color = Qt.GlobalColor.black if self.is_dark_theme else Qt.GlobalColor.white
        img.fill(bg_color)
        painter = QtGui.QPainter(img)
        painter.setRenderHints(
            QtGui.QPainter.RenderHint.Antialiasing | QtGui.QPainter.RenderHint.TextAntialiasing | QtGui.QPainter.RenderHint.SmoothPixmapTransform)
        scene.render(painter, QtCore.QRectF(img.rect()), src_rect)
        painter.end()
        base_name = os.path.splitext(os.path.basename(vd.file_path or f'view_{idx + 1}'))[0]
        default_name = f"{base_name}_export.png"
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, f"Экспорт окна {idx + 1}", default_name,
                                                              "PNG (*.png);;JPEG (*.jpg *.jpeg);;BMP (*.bmp)")
        if file_path:
            if not img.save(file_path, quality=100):
                QtWidgets.QMessageBox.warning(self, "Экспорт", f"Ошибка сохранения файла: {file_path}")
            else:
                QtWidgets.QMessageBox.information(self, "Экспорт", f"Изображение сохранено:\n{file_path}")

    def set_tool_for_visible_views(self, tool_name):
        self.toolbar.set_tool_for_visible_views(tool_name)
        visible_views = self._get_current_views()
        for view in visible_views:
            view.set_tool_mode(tool_name)
        if tool_name == ToolManager.TOOL_ZOOM_CENTER and self.current_mode_index == 1 and len(visible_views) == 2:
            visible_views[0]._paired_view = visible_views[1]
            visible_views[1]._paired_view = visible_views[0]
        else:
            for view in visible_views:
                view._paired_view = None

    def _get_current_tool(self):
        action = self.toolbar.tool_group.checkedAction()
        return action.data() if action and action.data() else ToolManager.TOOL_NONE

    def _get_visible_data_indices(self):
        return [i for i, v in enumerate(self.all_views) if v.isVisible() and self.view_data[i].pixmap_item is not None]

    def zoom_in(self):
        for i in self._get_visible_data_indices():
            view = self.all_views[i]
            view.scale(1.15, 1.15)
            view.update_overlay_scaling()
            self._update_image_overlay(i)

    def zoom_out(self):
        for i in self._get_visible_data_indices():
            view = self.all_views[i]
            view.scale(1 / 1.15, 1 / 1.15)
            view.update_overlay_scaling()
            self._update_image_overlay(i)

    def reset_view(self):
        for i in self._get_visible_data_indices():
            view = self.all_views[i]
            vd = self.view_data[i]
            item = vd.pixmap_item
            if not item:
                continue
            vd.rotation = 0
            vd.flip_h = False
            vd.flip_v = False
            self._apply_item_transformations(i)
            view.resetTransform()
            scene_rect = item.sceneBoundingRect()
            if scene_rect.isValid() and not scene_rect.isEmpty():
                view.fitInView(scene_rect, Qt.AspectRatioMode.KeepAspectRatio)
            view.update_overlay_scaling()
            self._update_image_overlay(i)

    def rotate_image(self):
        for i in self._get_visible_data_indices():
            vd = self.view_data[i]
            vd.rotation = (vd.rotation + 90) % 360
            self._apply_item_transformations(i)
            self._update_view_after_transform(i)

    def flip_horizontal(self):
        for i in self._get_visible_data_indices():
            vd = self.view_data[i]
            vd.flip_h = not vd.flip_h
            self._apply_item_transformations(i)
            self._update_view_after_transform(i)

    def flip_vertical(self):
        for i in self._get_visible_data_indices():
            vd = self.view_data[i]
            vd.flip_v = not vd.flip_v
            self._apply_item_transformations(i)
            self._update_view_after_transform(i)

    def show_study_info_dialog(self):
        from ui.dialogs.info_dialog import DicomInfoDialog
        idx = self.last_active_view_index
        if not (0 <= idx < MAX_VIEWS):
            return
        vd = self.view_data[idx]
        if not vd.file_path:
            QtWidgets.QMessageBox.information(self, "Инфо", f"Нет данных для окна {idx + 1}.")
            return
        current_zoom = self.all_views[idx].transform().m11() if self.all_views[idx] else 1.0
        dlg = DicomInfoDialog(idx, vd, current_zoom, self.brightness, self.contrast, self.negative_mode, self.is_dark_theme, self)
        dlg.exec()

    def open_adjustment_dialog(self):
        from ui.dialogs.adjustments_dialog import AdjustmentsDialog
        dlg = AdjustmentsDialog(self.brightness, self.contrast, self.negative_mode, self.is_dark_theme, self)
        dlg.brightnessChanged.connect(self._on_brightness_changed)
        dlg.contrastChanged.connect(self._on_contrast_changed)
        dlg.negativeChanged.connect(self._on_negative_changed)
        dlg.valuesApplied.connect(self._on_values_applied)
        dlg.valuesReset.connect(self._on_values_reset)
        dlg.exec()

    def _on_brightness_changed(self, value):
        self.brightness = value
        self._update_adjustments()

    def _on_contrast_changed(self, value):
        self.contrast = value / 100.0
        self._update_adjustments()

    def _on_negative_changed(self, checked):
        self.negative_mode = checked
        self._update_adjustments()

    def _on_values_applied(self, brightness, contrast, negative):
        self.brightness = brightness
        self.contrast = contrast / 100.0
        self.negative_mode = negative
        self._update_adjustments()

    def _on_values_reset(self):
        self.brightness = 0
        self.contrast = 1.0
        self.negative_mode = False
        self._update_adjustments()

    def toggle_theme(self):
        self.is_dark_theme = not self.is_dark_theme
        self.app_config['dark_theme'] = self.is_dark_theme
        self._apply_theme()
        visible_indices = self._get_visible_indices()
        for i in visible_indices:
            self._update_view_border(i, i == self.last_active_view_index)
            self._update_image_overlay(i)

    def _apply_theme(self):
        resources_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'resources')
        if self.is_dark_theme:
            qss_path = os.path.join(resources_dir, 'style_dark.qss')
        else:
            qss_path = os.path.join(resources_dir, 'style_light.qss')
        if os.path.exists(qss_path):
            with open(qss_path, 'r', encoding='utf-8') as f:
                self.setStyleSheet(f.read())
        else:
            if self.is_dark_theme:
                self.setStyleSheet("QMainWindow { background-color: #262624; color: #FAF9F5; }")
            else:
                self.setStyleSheet("QMainWindow { background-color: #FAF9F5; color: #141413; }")
        # Sync toolbar
        if hasattr(self, 'toolbar'):
            self.toolbar.is_dark_theme = self.is_dark_theme
            self.toolbar.update_toolbar_icons()
        # Toggle handle arrow color
        if hasattr(self, 'toggle_handle'):
            self.toggle_handle.setText("◀" if self.sidebar.isVisible() else "▶")

    def open_settings(self):
        from ui.dialogs.settings_dialog import SettingsDialog
        dlg = SettingsDialog(self.app_config, self)
        dlg.settingsChanged.connect(self._update_config)
        dlg.exec()

    def _update_config(self, new_config):
        self.app_config = new_config
        self.is_dark_theme = self.app_config['dark_theme']
        self._apply_theme()
        for view in self.all_views:
            view.note_color = QtGui.QColor(self.app_config['note_color'])
            view.set_low_quality_mode(self.app_config['low_quality'])
        font = QtWidgets.QApplication.font()
        if self.app_config['large_ui']:
            font.setPointSize(12)
            self.toolbar.setIconSize(QtCore.QSize(40, 40))
        else:
            font.setPointSize(9)
            self.toolbar.setIconSize(QtCore.QSize(24, 24))
        QtWidgets.QApplication.setFont(font)

    def open_help(self):
        from ui.dialogs.help_dialog import HelpDialog
        HelpDialog(self).exec()

    def dragEnterEvent(self, event):
        mime_data = event.mimeData()
        if mime_data.hasUrls():
            has_supported_files = False
            for url in mime_data.urls():
                if url.isLocalFile():
                    path = url.toLocalFile()
                    if os.path.isdir(path):
                        has_supported_files = True
                        break
                    elif os.path.isfile(path):
                        ext = os.path.splitext(path)[1].lower()
                        if ext in SUPPORTED_EXTS:
                            has_supported_files = True
                            break
            if has_supported_files:
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()

    def dropEvent(self, event):
        mime_data = event.mimeData()
        if mime_data.hasUrls():
            files_to_load = []
            for url in mime_data.urls():
                if url.isLocalFile():
                    path = url.toLocalFile()
                    if os.path.isdir(path):
                        try:
                            for root, _, files in os.walk(path):
                                for filename in files:
                                    ext = os.path.splitext(filename)[1].lower()
                                    if ext in SUPPORTED_EXTS:
                                        full_path = os.path.join(root, filename)
                                        files_to_load.append(full_path)
                        except Exception as e:
                            print(f"Ошибка сканирования папки {path}: {e}")
                    elif os.path.isfile(path):
                        ext = os.path.splitext(path)[1].lower()
                        if ext in SUPPORTED_EXTS:
                            files_to_load.append(path)
            if files_to_load:
                self.load_files(files_to_load)
                event.acceptProposedAction()
                return
        event.ignore()
