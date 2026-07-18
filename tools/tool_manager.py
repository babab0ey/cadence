import math
import numpy as np
from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtCore import Qt


class GraphicsItemCommand(QtGui.QUndoCommand):
    def __init__(self, scene, item, item_list_ref=None, action_type="add"):
        super().__init__(f"{action_type.capitalize()} Item")
        self.scene = scene
        self.item = item
        self.item_list_ref = item_list_ref
        self.action_type = action_type

    def redo(self):
        if self.action_type == "add":
            if self.item.scene() != self.scene:
                self.scene.addItem(self.item)
            if self.item_list_ref is not None and self.item not in self.item_list_ref:
                self.item_list_ref.append(self.item)
        else:
            if self.item.scene() == self.scene:
                self.scene.removeItem(self.item)
            if self.item_list_ref is not None and self.item in self.item_list_ref:
                self.item_list_ref.remove(self.item)

    def undo(self):
        if self.action_type == "add":
            if self.item.scene() == self.scene:
                self.scene.removeItem(self.item)
            if self.item_list_ref is not None and self.item in self.item_list_ref:
                self.item_list_ref.remove(self.item)
        else:
            if self.item.scene() != self.scene:
                self.scene.addItem(self.item)
            if self.item_list_ref is not None and self.item not in self.item_list_ref:
                self.item_list_ref.append(self.item)


class ToolManager:
    TOOL_NONE = "none"
    TOOL_RULER = "ruler"
    TOOL_PEN = "pen"
    TOOL_ROI = "roi"
    TOOL_ROI_ELLIPSE = "roi_ellipse"
    TOOL_POLYGON = "polygon"
    TOOL_ANGLE = "angle"
    TOOL_NOTE = "note"
    TOOL_ZOOM_CENTER = "zoom_center"

    DRAW_TOOLS = {TOOL_RULER, TOOL_PEN, TOOL_ROI, TOOL_ROI_ELLIPSE, TOOL_POLYGON, TOOL_ANGLE, TOOL_NOTE, TOOL_ZOOM_CENTER}

    @classmethod
    def is_draw_tool(cls, mode):
        return mode in cls.DRAW_TOOLS

    @classmethod
    def cursor_for_tool(cls, mode):
        if mode in cls.DRAW_TOOLS:
            return Qt.CursorShape.CrossCursor
        return Qt.CursorShape.ArrowCursor
