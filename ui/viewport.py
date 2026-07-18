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
from resources.design_tokens import GEOMETRY, theme_tokens


class SkeletonOverlay(QtWidgets.QWidget):
    """Theme-aware shimmer shown while a full-resolution image is decoded."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("skeletonOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._progress = 0.0
        self._dark = False
        self._text = "Открываю снимок…"
        self._shimmer = QtCore.QPropertyAnimation(self, b"shimmerProgress", self)
        self._shimmer.setStartValue(0.0)
        self._shimmer.setEndValue(1.0)
        self._shimmer.setDuration(1500)
        self._shimmer.setLoopCount(-1)
        self._shimmer.setEasingCurve(QtCore.QEasingCurve.Type.InOutSine)
        self._opacity = QtWidgets.QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity)
        self._fade = QtCore.QPropertyAnimation(self._opacity, b"opacity", self)
        self._fade.setDuration(GEOMETRY["transition_fast"])
        self._fade.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)
        self._fade.finished.connect(self._finish_fade)
        self.hide()

    @QtCore.pyqtProperty(float)
    def shimmerProgress(self):
        return self._progress

    @shimmerProgress.setter
    def shimmerProgress(self, value):
        self._progress = float(value)
        self.update()

    def set_theme(self, dark):
        self._dark = bool(dark)
        self.update()

    def start(self, text="Открываю снимок…"):
        self._text = text
        self._fade.stop()
        self._opacity.setOpacity(1.0)
        self.show()
        self.raise_()
        if self._shimmer.state() != QtCore.QAbstractAnimation.State.Running:
            self._shimmer.start()

    def stop(self):
        if not self.isVisible():
            return
        self._fade.stop()
        self._fade.setStartValue(self._opacity.opacity())
        self._fade.setEndValue(0.0)
        self._fade.start()

    def _finish_fade(self):
        if self._opacity.opacity() <= 0.01:
            self.hide()
            self._shimmer.stop()

    def paintEvent(self, _event):
        tokens = theme_tokens(self._dark)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QtGui.QColor(tokens["viewer_bg"]))
        margin_x = max(24, int(self.width() * 0.08))
        margin_y = max(24, int(self.height() * 0.08))
        card = self.rect().adjusted(margin_x, margin_y, -margin_x, -margin_y)
        base = QtGui.QColor(tokens["skeleton"])
        highlight = QtGui.QColor(tokens["skeleton_highlight"])
        band = max(100, int(card.width() * 0.22))
        center = card.left() - band + int((card.width() + band * 2) * self._progress)
        gradient = QtGui.QLinearGradient(center - band, 0, center + band, 0)
        gradient.setColorAt(0.0, base)
        gradient.setColorAt(0.5, highlight)
        gradient.setColorAt(1.0, base)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawRoundedRect(QtCore.QRectF(card), GEOMETRY["radius_lg"], GEOMETRY["radius_lg"])
        font = painter.font()
        font.setPixelSize(GEOMETRY["font_base"])
        font.setWeight(QtGui.QFont.Weight.Medium)
        painter.setFont(font)
        painter.setPen(QtGui.QColor("#F5F3EF"))
        painter.drawText(card.adjusted(0, 0, 0, -20), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom, self._text)


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
    frameChangeRequested = QtCore.pyqtSignal(QtWidgets.QGraphicsView, int)

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
        self.wheel_zoom_enabled = True

        self._loading_overlay = SkeletonOverlay(self.viewport())

        self._current_frame_index = 0
        self._frame_count = 1
        self._frame_request_timer = QtCore.QTimer(self)
        self._frame_request_timer.setSingleShot(True)
        self._frame_request_timer.setInterval(120)
        self._frame_request_timer.timeout.connect(self._emit_pending_frame_request)

        self._frame_controls = QtWidgets.QFrame(self.viewport())
        self._frame_controls.setObjectName("frameControls")
        frame_layout = QtWidgets.QHBoxLayout(self._frame_controls)
        frame_layout.setContentsMargins(8, 6, 8, 6)
        frame_layout.setSpacing(8)

        self._previous_frame_button = QtWidgets.QPushButton("‹")
        self._previous_frame_button.setObjectName("frameNavigationButton")
        self._previous_frame_button.setToolTip("Предыдущий кадр (Alt + колесо вниз)")
        self._previous_frame_button.setFixedSize(34, 34)
        self._previous_frame_button.clicked.connect(lambda: self._step_frame(-1))
        frame_layout.addWidget(self._previous_frame_button)

        self._frame_slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self._frame_slider.setObjectName("frameSlider")
        self._frame_slider.setMinimumWidth(110)
        self._frame_slider.valueChanged.connect(self._on_frame_slider_changed)
        self._frame_slider.sliderReleased.connect(self._emit_pending_frame_request)
        frame_layout.addWidget(self._frame_slider, stretch=1)

        self._frame_label = QtWidgets.QLabel("Кадр 1 / 1")
        self._frame_label.setObjectName("frameLabel")
        self._frame_label.setMinimumWidth(92)
        self._frame_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        frame_layout.addWidget(self._frame_label)

        self._next_frame_button = QtWidgets.QPushButton("›")
        self._next_frame_button.setObjectName("frameNavigationButton")
        self._next_frame_button.setToolTip("Следующий кадр (Alt + колесо вверх)")
        self._next_frame_button.setFixedSize(34, 34)
        self._next_frame_button.clicked.connect(lambda: self._step_frame(1))
        frame_layout.addWidget(self._next_frame_button)
        self._frame_controls.hide()

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
        self._loading_overlay.setGeometry(self.viewport().rect())
        if loading:
            self._loading_overlay.start(text)
        else:
            self._loading_overlay.stop()

    def apply_theme(self, dark):
        self._loading_overlay.set_theme(dark)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._loading_overlay.setGeometry(self.viewport().rect())
        self._position_frame_controls()

    def _position_frame_controls(self):
        if not self._frame_controls.isVisible():
            return
        self._frame_controls.adjustSize()
        available_width = max(180, self.viewport().width() - 24)
        control_width = min(self._frame_controls.sizeHint().width(), available_width)
        control_height = self._frame_controls.sizeHint().height()
        self._frame_controls.resize(control_width, control_height)
        self._frame_controls.move(
            max(12, (self.viewport().width() - control_width) // 2),
            max(12, self.viewport().height() - control_height - 14),
        )
        self._frame_controls.raise_()

    def set_frame_navigation(self, current_frame_index, frame_count):
        self._frame_count = max(1, int(frame_count or 1))
        self._current_frame_index = max(
            0,
            min(self._frame_count - 1, int(current_frame_index or 0)),
        )
        self._frame_request_timer.stop()
        blocked = self._frame_slider.blockSignals(True)
        self._frame_slider.setRange(0, self._frame_count - 1)
        self._frame_slider.setValue(self._current_frame_index)
        self._frame_slider.blockSignals(blocked)
        self._update_frame_label(self._current_frame_index)
        self._previous_frame_button.setEnabled(self._current_frame_index > 0)
        self._next_frame_button.setEnabled(self._current_frame_index < self._frame_count - 1)
        self._frame_controls.setVisible(self._frame_count > 1)
        if self._frame_controls.isVisible():
            self._position_frame_controls()

    def _update_frame_label(self, frame_index):
        self._frame_label.setText(f"Кадр {frame_index + 1} / {self._frame_count}")

    def _on_frame_slider_changed(self, frame_index):
        self._update_frame_label(frame_index)
        self._previous_frame_button.setEnabled(frame_index > 0)
        self._next_frame_button.setEnabled(frame_index < self._frame_count - 1)
        self._frame_request_timer.start()

    def _emit_pending_frame_request(self):
        self._frame_request_timer.stop()
        target = self._frame_slider.value()
        if self._frame_count > 1 and target != self._current_frame_index:
            self.frameChangeRequested.emit(self, target)

    def _step_frame(self, direction):
        target = max(
            0,
            min(self._frame_count - 1, self._frame_slider.value() + int(direction)),
        )
        if target == self._frame_slider.value():
            return
        self._frame_slider.setValue(target)
        self._emit_pending_frame_request()

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

    def _viewer_window(self):
        parent = self.parent()
        while parent and not hasattr(parent, "view_data"):
            parent = parent.parent()
        return parent

    def _main_view_drag_payload(self):
        try:
            view_index = int(self.objectName().split("_")[-1])
        except (TypeError, ValueError, IndexError):
            return ""
        viewer = self._viewer_window()
        if viewer is None or not (0 <= view_index < len(viewer.view_data)):
            return ""
        file_path = viewer.view_data[view_index].file_path or ""
        return f"main_view_file_{view_index}_{file_path}"

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
                    viewer = self._viewer_window()
                    source_is_valid = (
                        viewer is not None
                        and 0 <= source_idx < len(viewer.view_data)
                        and viewer.view_data[source_idx].file_path == file_path
                    )
                    if source_is_valid:
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
            payload = self._main_view_drag_payload()
            if not payload:
                return
            mime_data.setText(payload)
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
        if (
            self._frame_count > 1
            and bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)
        ):
            self._step_frame(1 if angle_delta > 0 else -1)
            event.accept()
            return
        if not self.wheel_zoom_enabled:
            event.ignore()
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
        self.set_frame_navigation(0, 1)
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
