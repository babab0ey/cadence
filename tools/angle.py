import math
from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtCore import Qt
from tools.tool_manager import GraphicsItemCommand


class AngleTool:
    def __init__(self, view):
        self.view = view
        self.angle_points = []
        self.angle_line1 = None
        self.angle_line2 = None
        self.angle_text = None

    def on_press(self, pos, scene, scale):
        pen_width = max(1.0, 2.0 / scale) if scale > 1e-6 else 2.0
        pen = QtGui.QPen(Qt.GlobalColor.magenta, pen_width, Qt.PenStyle.SolidLine,
                         Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        if len(self.angle_points) == 0 or len(self.angle_points) == 3:
            self._cleanup_temp(scene)
        self.angle_points.append(pos)
        if len(self.angle_points) == 2:
            p1, p2 = self.angle_points
            if self.angle_line1 and self.angle_line1.scene() == scene:
                scene.removeItem(self.angle_line1)
            self.angle_line1 = scene.addLine(QtCore.QLineF(p1, p2), pen)
            self.angle_line1.setZValue(5)
        elif len(self.angle_points) == 3:
            p1, p2, p3 = self.angle_points
            if self.angle_line1:
                self.angle_line1.setLine(QtCore.QLineF(p1, p2))
                self.angle_line1.setPen(pen)
            else:
                self.angle_line1 = scene.addLine(QtCore.QLineF(p1, p2), pen)
                self.angle_line1.setZValue(5)
            if self.angle_line2 and self.angle_line2.scene() == scene:
                scene.removeItem(self.angle_line2)
            if self.angle_text and self.angle_text.scene() == scene:
                scene.removeItem(self.angle_text)
            self.angle_line2 = scene.addLine(QtCore.QLineF(p2, p3), pen)
            self.angle_line2.setZValue(5)
            v1 = p1 - p2
            v2 = p3 - p2
            n1 = math.hypot(v1.x(), v1.y())
            n2 = math.hypot(v2.x(), v2.y())
            angle_deg = 0.0
            cos_angle = -2.0
            if n1 * n2 > 1e-9:
                dot = QtCore.QPointF.dotProduct(v1, v2)
                cos_angle = max(-1.0, min(1.0, dot / (n1 * n2)))
                try:
                    angle_deg = math.degrees(math.acos(cos_angle))
                except ValueError:
                    angle_deg = 0.0 if dot >= 0 else 180.0
            self.angle_text = scene.addSimpleText(f"{angle_deg:.1f}°")
            self.angle_text.setBrush(Qt.GlobalColor.darkMagenta)
            font_size = max(8, int(10 / scale)) if scale > 1e-6 else 10
            self.angle_text.setFont(QtGui.QFont("Arial", font_size))
            self.angle_text.setZValue(6)
            self.angle_text._is_measurement_text = True
            offset_val = 10.0 / scale if scale > 1e-6 else 10.0
            try:
                angle_rad = math.acos(cos_angle)
                angle_v1_rad = math.atan2(v1.y(), v1.x())
                cross_product_z = v1.x() * v2.y() - v1.y() * v2.x()
                bisector_offset_rad = angle_rad / 2.0
                mid_angle_rad = angle_v1_rad + bisector_offset_rad
                normal_angle_rad = mid_angle_rad + (math.pi / 2 * (-1 if cross_product_z < 0 else 1))
                text_offset_x = offset_val * math.cos(normal_angle_rad)
                text_offset_y = offset_val * math.sin(normal_angle_rad)
                self.angle_text.setPos(p2 + QtCore.QPointF(text_offset_x, text_offset_y))
            except Exception:
                self.angle_text.setPos(p2 + QtCore.QPointF(offset_val, -offset_val))
            self._finalize(scene, scale)

    def on_move(self, pos, scene, scale):
        if not scene:
            return
        pen_width = max(1.0, 2.0 / scale) if scale > 1e-6 else 2.0
        pen = QtGui.QPen(Qt.GlobalColor.magenta, pen_width, Qt.PenStyle.SolidLine,
                         Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        if len(self.angle_points) == 1:
            p1 = self.angle_points[0]
            if self.angle_line1:
                self.angle_line1.setLine(QtCore.QLineF(p1, pos))
                self.angle_line1.setPen(pen)
            else:
                self.angle_line1 = scene.addLine(QtCore.QLineF(p1, pos), pen)
                self.angle_line1.setZValue(5)
            if self.angle_line2 and self.angle_line2.scene() == scene:
                scene.removeItem(self.angle_line2)
            self.angle_line2 = None
            if self.angle_text and self.angle_text.scene() == scene:
                scene.removeItem(self.angle_text)
            self.angle_text = None
        elif len(self.angle_points) == 2:
            p1, p2 = self.angle_points
            if self.angle_line1:
                self.angle_line1.setLine(QtCore.QLineF(p1, p2))
                self.angle_line1.setPen(pen)
            else:
                self.angle_line1 = scene.addLine(QtCore.QLineF(p1, p2), pen)
                self.angle_line1.setZValue(5)
            if self.angle_line2:
                self.angle_line2.setLine(QtCore.QLineF(p2, pos))
                self.angle_line2.setPen(pen)
            else:
                self.angle_line2 = scene.addLine(QtCore.QLineF(p2, pos), pen)
                self.angle_line2.setZValue(5)
            if self.angle_text and self.angle_text.scene() == scene:
                scene.removeItem(self.angle_text)
            self.angle_text = None

    def on_release(self, pos, scene, scale):
        if len(self.angle_points) == 3:
            pen_width = max(1.0, 2.0 / scale) if scale > 1e-6 else 2.0
            pen = QtGui.QPen(Qt.GlobalColor.magenta, pen_width, Qt.PenStyle.SolidLine,
                             Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            if self.angle_line1:
                self.angle_line1.setPen(pen)
            if self.angle_line2:
                self.angle_line2.setPen(pen)

    def _finalize(self, scene, scale):
        items_to_group = []
        if self.angle_line1:
            items_to_group.append(self.angle_line1)
        if self.angle_line2:
            items_to_group.append(self.angle_line2)
        if self.angle_text:
            items_to_group.append(self.angle_text)
        if items_to_group:
            group = scene.createItemGroup(items_to_group)
            self.view.undo_stack.push(GraphicsItemCommand(scene, group, self.view.measurement_items))
        self.angle_line1 = None
        self.angle_line2 = None
        self.angle_text = None
        self.angle_points = []

    def _cleanup_temp(self, scene):
        items_to_remove = [self.angle_line1, self.angle_line2, self.angle_text]
        for item in items_to_remove:
            if item and item.scene() == scene:
                try:
                    scene.removeItem(item)
                except Exception:
                    pass
        self.angle_points = []
        self.angle_line1 = None
        self.angle_line2 = None
        self.angle_text = None

    def full_cleanup(self, scene):
        self._cleanup_temp(scene)

    def clear_incomplete(self, scene):
        if self.angle_line1 and len(self.angle_points) < 2 and self.angle_line1.scene() == scene:
            scene.removeItem(self.angle_line1)
            self.angle_line1 = None
        if self.angle_line2 and len(self.angle_points) < 3 and self.angle_line2.scene() == scene:
            scene.removeItem(self.angle_line2)
            self.angle_line2 = None
