import math
import numpy as np
from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtCore import Qt
from tools.tool_manager import GraphicsItemCommand


class RoiRectTool:
    def __init__(self, view):
        self.view = view
        self.roi_start = None
        self.roi_rect_item = None
        self.roi_text = None

    def on_press(self, pos, scene, scale):
        self.clear_temp(scene)
        self.roi_start = pos

    def on_move(self, pos, scene, scale):
        if not self.roi_start or not scene:
            return
        rect = QtCore.QRectF(self.roi_start, pos).normalized()
        pen_width = max(1.0, 2.0 / scale) if scale > 1e-6 else 2.0
        pen = QtGui.QPen(Qt.PenStyle.SolidLine)
        pen.setWidthF(pen_width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        pen.setColor(Qt.GlobalColor.blue)
        pen.setStyle(Qt.PenStyle.DashLine)
        if not self.roi_rect_item:
            self.roi_rect_item = scene.addRect(rect, pen)
            brush = QtGui.QBrush(QtGui.QColor(0, 0, 255, 50))
            self.roi_rect_item.setBrush(brush)
            self.roi_rect_item.setZValue(5)
        else:
            self.roi_rect_item.setRect(rect)
            self.roi_rect_item.setPen(pen)
        if self.roi_text and self.roi_text.scene() == scene:
            scene.removeItem(self.roi_text)
        self.roi_text = None

    def on_release(self, pos, scene, scale):
        if self.roi_start and self.roi_rect_item:
            self._finalize_roi(self.roi_rect_item, "rect", scene, scale)
        self.roi_start = None
        self.roi_rect_item = None

    def clear_temp(self, scene):
        if self.roi_rect_item and self.roi_start is not None and self.roi_rect_item.scene() == scene:
            scene.removeItem(self.roi_rect_item)
        self.roi_rect_item = None

    def _finalize_roi(self, item, shape_type, scene, scale):
        rect = item.sceneBoundingRect()
        min_roi_dim = 3
        pen_width = max(1.0, 2.0 / scale) if scale > 1e-6 else 2.0
        font = QtGui.QFont("Arial", max(8, int(10 / scale)))

        if self.view.image_array_ref is not None and rect.width() >= min_roi_dim and rect.height() >= min_roi_dim:
            img_h, img_w = self.view.image_array_ref.shape[:2]
            x, y, w, h = map(int, map(round, [rect.x(), rect.y(), rect.width(), rect.height()]))
            x1, y1 = max(0, x), max(0, y)
            x2, y2 = min(img_w, x + w), min(img_h, y + h)
            if x2 > x1 and y2 > y1:
                region = self.view.image_array_ref[y1:y2, x1:x2]
                if region.size > 0:
                    stats = self._compute_stats(region, rect, shape_type)
                    if self.roi_text and self.roi_text.scene() == scene:
                        scene.removeItem(self.roi_text)
                    self.roi_text = scene.addSimpleText(stats)
                    self.roi_text.setBrush(Qt.GlobalColor.darkBlue)
                    self.roi_text.setFont(font)
                    self.roi_text.setZValue(6)
                    self.roi_text._is_measurement_text = True
                    offset = 5.0 / scale if scale > 1e-6 else 5.0
                    self.roi_text.setPos(rect.topLeft() + QtCore.QPointF(offset, offset))
                    final_pen = item.pen()
                    final_pen.setStyle(Qt.PenStyle.SolidLine)
                    final_pen.setWidthF(pen_width)
                    item.setPen(final_pen)
                    group = scene.createItemGroup([item, self.roi_text])
                    self.view.undo_stack.push(GraphicsItemCommand(scene, group, self.view.measurement_items))
                    self.roi_text = None
                    self._ask_save_roi(rect)
                    return

        if item.scene() == scene:
            scene.removeItem(item)
        if self.roi_text and self.roi_text.scene() == scene:
            scene.removeItem(self.roi_text)
        self.roi_text = None

    def _compute_stats(self, region, rect, shape_type):
        region_float = region.astype(np.float64)
        mean_val = np.mean(region_float)
        std_val = np.std(region_float)
        min_val_disp = np.min(region_float)
        max_val_disp = np.max(region_float)
        area_px = region.size
        if shape_type == "ellipse":
            area_px = math.pi * (rect.width() / 2) * (rect.height() / 2)
        pixel_spacing = self.view.pixel_spacing
        area_unit = "mm²"
        area_val = area_px * (pixel_spacing ** 2)
        if abs(pixel_spacing - 1.0) < 1e-9:
            area_unit = "px²"
            area_val = area_px
        return (f"Mean: {mean_val:.1f}\nStdDev: {std_val:.1f}\nMin: {min_val_disp:.1f}\n"
                f"Max: {max_val_disp:.1f}\nArea: {area_val:.1f} {area_unit}")

    def _ask_save_roi(self, rect):
        reply = QtWidgets.QMessageBox.question(
            self.view, 'Сохранить ROI',
            'Хотите сохранить выделенную область как изображение?',
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            self._export_roi_area(rect)

    def _export_roi_area(self, roi_rect):
        if self.view.image_array_ref is None or not roi_rect.isValid():
            return False
        from core.utils import convert_numpy_to_qimage
        img_h, img_w = self.view.image_array_ref.shape[:2]
        x, y, w, h = map(int, map(round, [roi_rect.x(), roi_rect.y(), roi_rect.width(), roi_rect.height()]))
        x1, y1 = max(0, x), max(0, y)
        x2, y2 = min(img_w, x + w), min(img_h, y + h)
        if x2 > x1 and y2 > y1:
            roi_region = self.view.image_array_ref[y1:y2, x1:x2]
            if roi_region.size > 0:
                roi_qimage = convert_numpy_to_qimage(roi_region)
                if not roi_qimage.isNull():
                    file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
                        self.view, "Сохранить ROI область",
                        f"roi_region_{x1}_{y1}_{x2 - x1}x{y2 - y1}.png",
                        "PNG (*.png);;JPEG (*.jpg *.jpeg);;BMP (*.bmp);;TIFF (*.tif *.tiff)"
                    )
                    if file_path:
                        if not roi_qimage.save(file_path, quality=95):
                            QtWidgets.QMessageBox.warning(self.view, "Ошибка", f"Не удалось сохранить ROI область: {file_path}")
                            return False
                        else:
                            QtWidgets.QMessageBox.information(self.view, "Успех", f"ROI область сохранена: {file_path}")
                            return True
        return False


class RoiEllipseTool:
    def __init__(self, view):
        self.view = view
        self.roi_start = None
        self.roi_ellipse_item = None
        self.roi_text = None

    def on_press(self, pos, scene, scale):
        self.clear_temp(scene)
        self.roi_start = pos

    def on_move(self, pos, scene, scale):
        if not self.roi_start or not scene:
            return
        rect = QtCore.QRectF(self.roi_start, pos).normalized()
        pen_width = max(1.0, 2.0 / scale) if scale > 1e-6 else 2.0
        pen = QtGui.QPen(Qt.PenStyle.SolidLine)
        pen.setWidthF(pen_width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        pen.setColor(Qt.GlobalColor.cyan)
        pen.setStyle(Qt.PenStyle.DashLine)
        if not self.roi_ellipse_item:
            self.roi_ellipse_item = scene.addEllipse(rect, pen)
            brush = QtGui.QBrush(QtGui.QColor(0, 255, 255, 50))
            self.roi_ellipse_item.setBrush(brush)
            self.roi_ellipse_item.setZValue(5)
        else:
            self.roi_ellipse_item.setRect(rect)
        if self.roi_text and self.roi_text.scene() == scene:
            scene.removeItem(self.roi_text)
        self.roi_text = None

    def on_release(self, pos, scene, scale):
        if self.roi_start and self.roi_ellipse_item:
            self._finalize_roi(self.roi_ellipse_item, "ellipse", scene, scale)
        self.roi_start = None
        self.roi_ellipse_item = None

    def clear_temp(self, scene):
        if self.roi_ellipse_item and self.roi_start is not None and self.roi_ellipse_item.scene() == scene:
            scene.removeItem(self.roi_ellipse_item)
        self.roi_ellipse_item = None

    def _finalize_roi(self, item, shape_type, scene, scale):
        rect_tool = RoiRectTool(self.view)
        rect_tool.roi_text = self.roi_text
        rect_tool._finalize_roi(item, shape_type, scene, scale)
        self.roi_text = rect_tool.roi_text


class PolygonTool:
    def __init__(self, view):
        self.view = view
        self.polygon_points = []
        self.polygon_item = None

    def on_press(self, pos, scene, scale):
        self.polygon_points.append(pos)
        if not self.polygon_item:
            self.polygon_item = QtWidgets.QGraphicsPolygonItem()
            pen_width = max(1.0, 2.0 / scale) if scale > 1e-6 else 2.0
            pen = QtGui.QPen(Qt.PenStyle.SolidLine)
            pen.setWidthF(pen_width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            pen.setColor(Qt.GlobalColor.blue)
            pen.setStyle(Qt.PenStyle.DashLine)
            self.polygon_item.setPen(pen)
            self.polygon_item.setBrush(QtGui.QBrush(QtGui.QColor(0, 0, 255, 50)))
            self.polygon_item.setZValue(5)
            scene.addItem(self.polygon_item)
        poly = QtGui.QPolygonF(self.polygon_points)
        self.polygon_item.setPolygon(poly)

    def on_move(self, pos, scene, scale):
        if not self.polygon_points or not self.polygon_item:
            return
        temp_points = self.polygon_points + [pos]
        self.polygon_item.setPolygon(QtGui.QPolygonF(temp_points))

    def on_release(self, pos, scene, scale):
        pass

    def finish_polygon(self, scene, scale):
        if self.polygon_item and len(self.polygon_points) > 2:
            rect_tool = RoiRectTool(self.view)
            rect_tool._finalize_roi(self.polygon_item, "polygon", scene, scale)
        elif self.polygon_item and self.polygon_item.scene() == scene:
            scene.removeItem(self.polygon_item)
        self.polygon_points = []
        self.polygon_item = None

    def clear_temp(self, scene):
        if self.polygon_item and self.polygon_item.scene() == scene:
            scene.removeItem(self.polygon_item)
        self.polygon_points = []
        self.polygon_item = None
