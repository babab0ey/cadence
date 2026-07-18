import re
import math
from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtCore import Qt
from tools.tool_manager import ToolManager
from tools.ruler import RulerTool
from tools.angle import AngleTool
from tools.roi_shapes import RoiRectTool, RoiEllipseTool, PolygonTool
from tools.pen import PenTool
from tools.note import NoteTool


class InteractiveGraphicsView(QtWidgets.QGraphicsView):
    loadImageRequested = QtCore.pyqtSignal(QtWidgets.QGraphicsView)
    viewClicked = QtCore.pyqtSignal(QtWidgets.QGraphicsView)
    roiSaveRequested = QtCore.pyqtSignal(QtWidgets.QGraphicsView, QtCore.QRectF)
    singleViewToggleRequested = QtCore.pyqtSignal(QtWidgets.QGraphicsView)
    viewDropOccurred = QtCore.pyqtSignal(int, int)
    sidebarFileDropped = QtCore.pyqtSignal(int, str)
    windowLevelStarted = QtCore.pyqtSignal(QtWidgets.QGraphicsView)
    windowLevelChanged = QtCore.pyqtSignal(QtWidgets.QGraphicsView, int, int)
    windowLevelFinished = QtCore.pyqtSignal(QtWidgets.QGraphicsView)

    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.tool_mode = ToolManager.TOOL_NONE
        self.setMouseTracking(True)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QtWidgets.QGraphicsView.DragMode.NoDrag)
        self.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        self.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, True)
        self.setAcceptDrops(True)

        self.undo_stack = QtGui.QUndoStack(self)
        self.measurement_items = []

        self._ruler_tool = RulerTool(self)
        self._angle_tool = AngleTool(self)
        self._roi_rect_tool = RoiRectTool(self)
        self._roi_ellipse_tool = RoiEllipseTool(self)
        self._polygon_tool = PolygonTool(self)
        self._pen_tool = PenTool(self)
        self._note_tool = NoteTool(self)

        self.image_array_ref = None
        self.pixel_spacing = 1.0
        self.pixmap_item_ref = None
        self._is_panning = False
        self._pan_button = Qt.MouseButton.NoButton
        self._pan_start_pos = QtCore.QPoint()
        self._is_window_leveling = False
        self._wl_start_pos = QtCore.QPoint()
        self._wl_hint_shown = False
        self._drag_start_pos = QtCore.QPoint()
        self._zoom_factor = 1.0
        self._min_zoom = 0.1
        self._max_zoom = 10.0
        self._paired_view = None
        self._zoom_start_pos = None
        self.view_data = None
        self.is_low_quality = False

        self._loading_overlay = QtWidgets.QFrame(self.viewport())
        self._loading_overlay.setObjectName("loadingOverlay")
        self._loading_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        loading_layout = QtWidgets.QVBoxLayout(self._loading_overlay)
        loading_layout.setContentsMargins(32, 32, 32, 32)
        loading_layout.addStretch()
        self._loading_label = QtWidgets.QLabel("Открываю снимок…")
        self._loading_label.setObjectName("loadingLabel")
        self._loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_layout.addWidget(self._loading_label)
        self._loading_progress = QtWidgets.QProgressBar()
        self._loading_progress.setRange(0, 0)
        self._loading_progress.setTextVisible(False)
        self._loading_progress.setMaximumWidth(220)
        loading_layout.addWidget(self._loading_progress, alignment=Qt.AlignmentFlag.AlignHCenter)
        loading_layout.addStretch()
        self._loading_overlay.hide()

    @property
    def note_color(self):
        return self._note_tool.note_color

    @note_color.setter
    def note_color(self, value):
        self._note_tool.note_color = value

    @property
    def pen_items(self):
        return self._pen_tool.pen_items

    @property
    def text_notes(self):
        return self._note_tool.text_notes

    def set_low_quality_mode(self, enabled):
        self.is_low_quality = enabled
        self.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, not enabled)
        self.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, not enabled)

    def set_loading(self, loading, text="Открываю снимок…"):
        self._loading_label.setText(text)
        self._loading_overlay.setGeometry(self.viewport().rect())
        self._loading_overlay.setVisible(bool(loading))
        if loading:
            self._loading_overlay.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._loading_overlay.setGeometry(self.viewport().rect())

    def dragEnterEvent(self, event):
        mime_data = event.mimeData()
        if mime_data.hasText() and mime_data.text().startswith('view_swap_'):
            source_index = int(mime_data.text().split('_')[-1])
            target_index = int(self.objectName().split('_')[-1])
            if source_index != target_index:
                event.acceptProposedAction()
        elif mime_data.hasText() and mime_data.text().startswith('sidebar_file_'):
            event.acceptProposedAction()
        elif mime_data.hasText() and mime_data.text().startswith('main_view_file_'):
            event.acceptProposedAction()
        elif mime_data.hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dropEvent(self, event):
        mime_data = event.mimeData()
        if mime_data.hasText() and mime_data.text().startswith('view_swap_'):
            try:
                source_index = int(mime_data.text().split('_')[-1])
                target_index = int(self.objectName().split('_')[-1])
                if source_index != target_index:
                    self.viewDropOccurred.emit(source_index, target_index)
                    event.acceptProposedAction()
                return
            except Exception:
                pass
            event.ignore()
            return

        if mime_data.hasText() and mime_data.text().startswith('sidebar_file_'):
            try:
                file_path = mime_data.text().replace('sidebar_file_', '', 1)
                target_index = int(self.objectName().split('_')[-1])
                self.sidebarFileDropped.emit(target_index, file_path)
                event.acceptProposedAction()
                return
            except Exception:
                pass
            event.ignore()
            return

        if mime_data.hasText() and mime_data.text().startswith('main_view_file_'):
            try:
                text = mime_data.text()
                m = re.match(r'^main_view_file_(\d+)_(.+)$', text)
                if not m:
                    event.ignore()
                    return
                source_idx = int(m.group(1))
                file_path = m.group(2)
                target_idx = int(self.objectName().split('_')[-1])
                if source_idx != target_idx:
                    parent = self.parent()
                    while parent and not hasattr(parent, 'view_data'):
                        parent = parent.parent()
                    if parent and parent.view_data[source_idx].get('file_path') == file_path:
                        self.viewDropOccurred.emit(source_idx, target_idx)
                        event.acceptProposedAction()
                        return
            except Exception:
                pass
            event.ignore()
            return

        if mime_data.hasUrls():
            super().dropEvent(event)
        else:
            event.ignore()

    def mouseDoubleClickEvent(self, event):
        if self.tool_mode == ToolManager.TOOL_POLYGON:
            self._polygon_tool.finish_polygon(self.scene(), self.transform().m11())
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            from tools.note import TextNoteItem
            item = self.itemAt(event.position().toPoint())
            if isinstance(item, TextNoteItem):
                super().mouseDoubleClickEvent(event)
                return
            if self.pixmap_item_ref is not None:
                self.singleViewToggleRequested.emit(self)
                event.accept()
                return
            else:
                self.loadImageRequested.emit(self)
                event.accept()
                return
        else:
            super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event):
        self.viewClicked.emit(self)
        mouse_pos = event.position().toPoint()

        if event.button() == Qt.MouseButton.RightButton and self.pixmap_item_ref:
            self._is_window_leveling = True
            self._wl_start_pos = mouse_pos
            self.setCursor(Qt.CursorShape.SizeAllCursor)
            self.windowLevelStarted.emit(self)
            if not self._wl_hint_shown:
                self._wl_hint_shown = True
                QtWidgets.QToolTip.showText(
                    event.globalPosition().toPoint(),
                    "Зажмите правую кнопку и двигайте мышь:\n← → контраст, ↑ ↓ яркость",
                    self,
                    QtCore.QRect(),
                    4200,
                )
            event.accept()
            return

        wants_pan = (
            event.button() == Qt.MouseButton.MiddleButton
            or (
                event.button() == Qt.MouseButton.LeftButton
                and bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            )
        )
        if wants_pan and self.pixmap_item_ref:
            self._is_panning = True
            self._pan_button = event.button()
            self._pan_start_pos = mouse_pos
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton and self.pixmap_item_ref:
            self._drag_start_pos = mouse_pos

        if event.button() == Qt.MouseButton.LeftButton:
            if not self.pixmap_item_ref and self.tool_mode == ToolManager.TOOL_NONE:
                self.loadImageRequested.emit(self)
                event.accept()
                return
            elif not self.pixmap_item_ref:
                super().mousePressEvent(event)
                return

            pos = self.mapToScene(mouse_pos)
            scene = self.scene()
            if not scene:
                return
            scale = self.transform().m11()

            if self.tool_mode == ToolManager.TOOL_RULER:
                self._ruler_tool.on_press(pos, scene, scale)
            elif self.tool_mode == ToolManager.TOOL_PEN:
                self._pen_tool.on_press(pos, scene, scale)
            elif self.tool_mode == ToolManager.TOOL_ROI:
                self._roi_rect_tool.on_press(pos, scene, scale)
            elif self.tool_mode == ToolManager.TOOL_ROI_ELLIPSE:
                self._roi_ellipse_tool.on_press(pos, scene, scale)
            elif self.tool_mode == ToolManager.TOOL_POLYGON:
                self._polygon_tool.on_press(pos, scene, scale)
            elif self.tool_mode == ToolManager.TOOL_NOTE:
                self._note_tool.on_press(pos, scene, scale)
                event.accept()
                return
            elif self.tool_mode == ToolManager.TOOL_ANGLE:
                self._angle_tool.on_press(pos, scene, scale)
            elif self.tool_mode == ToolManager.TOOL_ZOOM_CENTER:
                self._zoom_start_pos = mouse_pos
                self._zoom_center = self.mapToScene(self.viewport().rect().center())
                event.accept()
                return
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        mouse_pos = event.position().toPoint()

        if self._is_window_leveling and bool(event.buttons() & Qt.MouseButton.RightButton):
            delta = mouse_pos - self._wl_start_pos
            self.windowLevelChanged.emit(self, delta.x(), delta.y())
            event.accept()
            return

        if self._is_panning and bool(event.buttons() & self._pan_button):
            delta = mouse_pos - self._pan_start_pos
            h_bar = self.horizontalScrollBar()
            v_bar = self.verticalScrollBar()
            h_bar.setValue(h_bar.value() - delta.x())
            v_bar.setValue(v_bar.value() - delta.y())
            self._pan_start_pos = mouse_pos
            event.accept()
            return

        if (event.buttons() & Qt.MouseButton.LeftButton) and self.pixmap_item_ref and self.tool_mode == ToolManager.TOOL_NONE:
            if (mouse_pos - self._drag_start_pos).manhattanLength() < QtWidgets.QApplication.startDragDistance():
                return
            drag = QtGui.QDrag(self)
            mime_data = QtCore.QMimeData()
            view_index = int(self.objectName().split('_')[-1])
            parent = self.parent()
            while parent and not hasattr(parent, 'view_data'):
                parent = parent.parent()
            file_path = ""
            if parent and hasattr(parent, 'view_data'):
                file_path = parent.view_data[view_index].get('file_path', "")
            mime_data.setText(f"main_view_file_{view_index}_{file_path}")
            drag.setMimeData(mime_data)
            if self.pixmap_item_ref:
                pixmap = self.pixmap_item_ref.pixmap().scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio,
                                                                Qt.TransformationMode.SmoothTransformation)
                hotSpot = QtCore.QPoint(pixmap.width() // 2, pixmap.height() // 2)
                drag.setPixmap(pixmap)
                drag.setHotSpot(hotSpot)
            drag.exec(Qt.DropAction.MoveAction)
            return

        if self.tool_mode != ToolManager.TOOL_NONE and event.buttons() == Qt.MouseButton.LeftButton:
            pos = self.mapToScene(mouse_pos)
            scene = self.scene()
            if not scene or not self.pixmap_item_ref:
                return
            scale = self.transform().m11()

            if self.tool_mode == ToolManager.TOOL_RULER:
                self._ruler_tool.on_move(pos, scene, scale)
            elif self.tool_mode == ToolManager.TOOL_PEN:
                self._pen_tool.on_move(pos, scene, scale)
            elif self.tool_mode == ToolManager.TOOL_ROI:
                self._roi_rect_tool.on_move(pos, scene, scale)
            elif self.tool_mode == ToolManager.TOOL_ROI_ELLIPSE:
                self._roi_ellipse_tool.on_move(pos, scene, scale)
            elif self.tool_mode == ToolManager.TOOL_ANGLE:
                self._angle_tool.on_move(pos, scene, scale)
            elif self.tool_mode == ToolManager.TOOL_ZOOM_CENTER and self._zoom_start_pos:
                current_pos = mouse_pos
                delta = current_pos - self._zoom_start_pos
                scale_factor = 1.0 + delta.y() / 100.0
                if scale_factor < 0.1:
                    scale_factor = 0.1
                self.scale(scale_factor, scale_factor)
                self.update_overlay_scaling()
                if self._paired_view:
                    self._paired_view.scale(scale_factor, scale_factor)
                    self._paired_view.update_overlay_scaling()
                self._zoom_start_pos = current_pos
                event.accept()
                return
            event.accept()
            return

        if self.tool_mode == ToolManager.TOOL_POLYGON and self._polygon_tool.polygon_points:
            pos = self.mapToScene(mouse_pos)
            temp_points = self._polygon_tool.polygon_points + [pos]
            if self._polygon_tool.polygon_item:
                self._polygon_tool.polygon_item.setPolygon(QtGui.QPolygonF(temp_points))

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        mouse_pos = event.position().toPoint()

        if event.button() == Qt.MouseButton.RightButton and self._is_window_leveling:
            self._is_window_leveling = False
            self.windowLevelFinished.emit(self)
            self.set_tool_mode(self.tool_mode)
            event.accept()
            return

        if event.button() == self._pan_button and self._is_panning:
            self._is_panning = False
            self._pan_button = Qt.MouseButton.NoButton
            self.set_tool_mode(self.tool_mode)
            event.accept()
            return

        if self.tool_mode != ToolManager.TOOL_NONE and event.button() == Qt.MouseButton.LeftButton:
            pos = self.mapToScene(mouse_pos)
            scene = self.scene()
            if not scene or not self.pixmap_item_ref:
                self.clear_temporary_drawing_items()
                return
            scale = self.transform().m11()

            if self.tool_mode == ToolManager.TOOL_RULER:
                self._ruler_tool.on_release(pos, scene, scale)
            elif self.tool_mode == ToolManager.TOOL_PEN:
                self._pen_tool.on_release(pos, scene, scale)
            elif self.tool_mode == ToolManager.TOOL_ROI:
                self._roi_rect_tool.on_release(pos, scene, scale)
            elif self.tool_mode == ToolManager.TOOL_ROI_ELLIPSE:
                self._roi_ellipse_tool.on_release(pos, scene, scale)
            elif self.tool_mode == ToolManager.TOOL_ANGLE:
                self._angle_tool.on_release(pos, scene, scale)
            elif self.tool_mode == ToolManager.TOOL_ZOOM_CENTER:
                self._zoom_start_pos = None
                event.accept()
                return
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        self.viewClicked.emit(self)
        angle_delta = event.angleDelta().y()
        if angle_delta == 0:
            return
        zoom_in = angle_delta > 0
        zoom_step = 1.15
        current_scale = self.transform().m11()
        if zoom_in and current_scale >= self._max_zoom:
            return
        elif not zoom_in and current_scale <= self._min_zoom:
            return
        factor = zoom_step if zoom_in else 1 / zoom_step
        self.scale(factor, factor)
        self._zoom_factor = self.transform().m11()
        self.update_overlay_scaling()
        parent = self.parent()
        if hasattr(parent, '_update_image_overlay') and hasattr(parent, 'get_view_index'):
            try:
                idx = parent.get_view_index(self)
                if idx != -1:
                    parent._update_image_overlay(idx)
            except Exception:
                pass
        event.accept()

    def update_overlay_scaling(self):
        scale = self.transform().m11()
        scene = self.scene()
        if scale < 1e-6 or not scene:
            return
        pen_width = max(1.0, 2.0 / scale)
        font_size = max(8, int(10 / scale))
        font = QtGui.QFont("Arial", font_size)
        text_offset_base = 5.0 / scale
        for item in scene.items():
            if hasattr(item, '_is_projection_overlay'):
                continue
            if item == self.pixmap_item_ref:
                continue
            if hasattr(item, '_is_dicom_overlay') and item._is_dicom_overlay:
                continue
            if hasattr(item, '_is_text_note') and item._is_text_note:
                note_font = QtGui.QFont("Arial", max(10, int(12 / scale)), QtGui.QFont.Weight.Bold)
                item.setFont(note_font)
                continue
            if isinstance(item, (QtWidgets.QGraphicsLineItem, QtWidgets.QGraphicsPathItem, QtWidgets.QGraphicsRectItem)):
                try:
                    pen = item.pen()
                    pen.setWidthF(pen_width)
                    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                    if hasattr(item, '_is_temp_roi') and item._is_temp_roi:
                        pen.setStyle(Qt.PenStyle.DashLine)
                    item.setPen(pen)
                except AttributeError:
                    pass
            elif isinstance(item, QtWidgets.QGraphicsSimpleTextItem):
                is_measurement = hasattr(item, '_is_measurement_text') and item._is_measurement_text
                if is_measurement:
                    item.setFont(font)

    def set_image_data(self, adjusted_array, pixel_spacing, pixmap_item):
        self.image_array_ref = adjusted_array
        self.pixel_spacing = pixel_spacing if pixel_spacing is not None and pixel_spacing > 1e-9 else 1.0
        self.pixmap_item_ref = pixmap_item

    def clear_image_data(self):
        if self.pixmap_item_ref and self.pixmap_item_ref.scene() == self.scene():
            try:
                self.scene().removeItem(self.pixmap_item_ref)
            except Exception:
                pass
        self.image_array_ref = None
        self.pixel_spacing = 1.0
        self.pixmap_item_ref = None
        self.clear_all_drawing_items()

    def set_tool_mode(self, mode):
        if self.tool_mode == ToolManager.TOOL_ANGLE and mode != ToolManager.TOOL_ANGLE:
            self._angle_tool.full_cleanup(self.scene())
        self.tool_mode = mode
        self.setDragMode(QtWidgets.QGraphicsView.DragMode.NoDrag)
        if mode != ToolManager.TOOL_ANGLE:
            self._angle_tool.angle_points = []
        if not self._is_panning:
            self.setCursor(ToolManager.cursor_for_tool(mode))

    def clear_temporary_drawing_items(self):
        scene = self.scene()
        if not scene:
            return
        self._ruler_tool.clear_temp(scene)
        self._pen_tool.clear_temp(scene)
        self._roi_rect_tool.clear_temp(scene)
        self._roi_ellipse_tool.clear_temp(scene)
        self._polygon_tool.clear_temp(scene)
        self._angle_tool.clear_incomplete(scene)

    def clear_all_drawing_items(self):
        self.undo_stack.clear()
        scene = self.scene()
        if not scene:
            return
        self._angle_tool.full_cleanup(scene)
        self._ruler_tool.clear_temp(scene)
        self._pen_tool.clear_all(scene)
        self._roi_rect_tool.clear_temp(scene)
        self._roi_ellipse_tool.clear_temp(scene)
        self._polygon_tool.clear_temp(scene)
        self._note_tool.clear_all(scene)
        for item in list(self.measurement_items):
            if item.scene() == scene:
                scene.removeItem(item)
        self.measurement_items.clear()
        self._ruler_tool.roi_text = None
        self._roi_rect_tool.roi_text = None
        self._roi_ellipse_tool.roi_text = None
        scene.update()
        self.viewport().update()
