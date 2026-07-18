import math
from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtCore import Qt
from tools.tool_manager import GraphicsItemCommand


class RulerTool:
    def __init__(self, view):
        self.view = view
        self.measure_start = None
        self.measure_line = None
        self.measure_text = None

    def on_press(self, pos, scene, scale):
        if self.measure_line and self.measure_line.scene() == scene:
            scene.removeItem(self.measure_line)
        if self.measure_text and self.measure_text.scene() == scene:
            scene.removeItem(self.measure_text)
        self.measure_line = None
        self.measure_text = None
        self.measure_start = pos

    def on_move(self, pos, scene, scale):
        if not self.measure_start or not scene:
            return
        pen_width = max(1.0, 2.0 / scale) if scale > 1e-6 else 2.0
        pen = QtGui.QPen(Qt.PenStyle.SolidLine)
        pen.setWidthF(pen_width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        pen.setColor(Qt.GlobalColor.red)
        if not self.measure_line:
            self.measure_line = scene.addLine(QtCore.QLineF(self.measure_start, pos), pen)
            self.measure_line.setZValue(5)
        else:
            self.measure_line.setLine(QtCore.QLineF(self.measure_start, pos))
            self.measure_line.setPen(pen)
        if self.measure_text and self.measure_text.scene() == scene:
            scene.removeItem(self.measure_text)
        self.measure_text = None

    def on_release(self, pos, scene, scale):
        if not self.measure_start or not self.measure_line or not scene:
            self.cleanup(scene)
            return
        line = self.measure_line.line()
        min_len_pixels = 2.0
        if line.length() >= min_len_pixels:
            pixel_spacing = self.view.pixel_spacing
            dist = line.length() * pixel_spacing
            unit = "mm"
            if abs(pixel_spacing - 1.0) < 1e-9:
                unit = "px"
                dist = line.length()
            mid_point = line.center()
            if self.measure_text and self.measure_text.scene() == scene:
                scene.removeItem(self.measure_text)
            font_size = max(8, int(10 / scale)) if scale > 1e-6 else 10
            font = QtGui.QFont("Arial", font_size)
            self.measure_text = scene.addSimpleText(f"{dist:.1f} {unit}")
            self.measure_text.setBrush(Qt.GlobalColor.darkRed)
            self.measure_text.setFont(font)
            self.measure_text.setZValue(6)
            self.measure_text._is_measurement_text = True
            offset = QtCore.QPointF(2.0 / scale if scale > 1e-6 else 2.0,
                                    -2.0 / scale if scale > 1e-6 else -2.0)
            self.measure_text.setPos(mid_point + offset)
            pen_width = max(1.0, 2.0 / scale) if scale > 1e-6 else 2.0
            final_pen = self.measure_line.pen()
            final_pen.setColor(Qt.GlobalColor.red)
            final_pen.setWidthF(pen_width)
            self.measure_line.setPen(final_pen)
            group = scene.createItemGroup([self.measure_line, self.measure_text])
            self.view.undo_stack.push(GraphicsItemCommand(scene, group, self.view.measurement_items))
            self.measure_start = None
            self.measure_line = None
            self.measure_text = None
        else:
            self.cleanup(scene)

    def cleanup(self, scene):
        if self.measure_line and self.measure_line.scene() == scene:
            scene.removeItem(self.measure_line)
        if self.measure_text and self.measure_text.scene() == scene:
            scene.removeItem(self.measure_text)
        self.measure_line = None
        self.measure_text = None
        self.measure_start = None

    def clear_temp(self, scene):
        """Use the cleanup contract shared by the other drawing tools."""
        self.cleanup(scene)
