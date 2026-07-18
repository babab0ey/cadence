from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtCore import Qt
from tools.tool_manager import GraphicsItemCommand


class PenTool:
    def __init__(self, view):
        self.view = view
        self.pen_path = None
        self.pen_item = None
        self.pen_items = []

    def on_press(self, pos, scene, scale):
        if self.pen_item is None:
            self.pen_path = QtGui.QPainterPath(pos)
            self.pen_item = QtWidgets.QGraphicsPathItem()
            pen_width = max(1.0, 2.0 / scale) if scale > 1e-6 else 2.0
            pen = QtGui.QPen(Qt.PenStyle.SolidLine)
            pen.setWidthF(pen_width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            pen.setColor(Qt.GlobalColor.green)
            self.pen_item.setPen(pen)
            self.pen_item.setPath(self.pen_path)
            scene.addItem(self.pen_item)
            self.pen_item.setZValue(5)

    def on_move(self, pos, scene, scale):
        if self.pen_path and self.pen_item:
            self.pen_path.lineTo(pos)
            self.pen_item.setPath(self.pen_path)
            pen = self.pen_item.pen()
            pen_width = max(1.0, 2.0 / scale) if scale > 1e-6 else 2.0
            if abs(pen.widthF() - pen_width) > 0.1:
                pen.setWidthF(pen_width)
                self.pen_item.setPen(pen)

    def on_release(self, pos, scene, scale):
        if self.pen_path and self.pen_item:
            self.pen_path.lineTo(pos)
            self.pen_item.setPath(self.pen_path)
            scale_val = scale
            min_pen_length = 1.0 / scale_val if scale_val > 1e-6 else 1.0
            if not self.pen_path.isEmpty() and self.pen_path.length() >= min_pen_length:
                pen_width = max(1.0, 2.0 / scale_val) if scale_val > 1e-6 else 2.0
                final_pen = self.pen_item.pen()
                final_pen.setWidthF(pen_width)
                self.pen_item.setPen(final_pen)
                self.pen_items.append(self.pen_item)
                self.view.undo_stack.push(GraphicsItemCommand(scene, self.pen_item, self.pen_items))
                self.pen_item = None
            else:
                if self.pen_item.scene() == scene:
                    scene.removeItem(self.pen_item)
                self.pen_item = None
            self.pen_path = None

    def clear_temp(self, scene):
        if self.pen_item and self.pen_path is not None and self.pen_item.scene() == scene:
            scene.removeItem(self.pen_item)
        self.pen_path = None
        self.pen_item = None

    def clear_all(self, scene):
        self.clear_temp(scene)
        for item in list(self.pen_items):
            if item and item.scene() == scene:
                scene.removeItem(item)
        self.pen_items.clear()
