from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtCore import Qt
from tools.tool_manager import GraphicsItemCommand


class TextNoteItem(QtWidgets.QGraphicsTextItem):
    def __init__(self, text="", parent=None, color=Qt.GlobalColor.blue):
        super().__init__(text, parent)
        self.setFlags(
            QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsFocusable
        )
        self.setZValue(20)
        self._is_text_note = True
        self.setDefaultTextColor(QtGui.QColor(color))
        self.bg_brush = QtGui.QBrush(QtGui.QColor(0, 0, 0, 100))
        font = QtGui.QFont("Arial", 12, QtGui.QFont.Weight.Bold)
        self.setFont(font)

    def paint(self, painter, option, widget):
        painter.setBrush(self.bg_brush)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(self.boundingRect())
        super().paint(painter, option, widget)

    def mouseDoubleClickEvent(self, event):
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.setFocus()
        super().mouseDoubleClickEvent(event)

    def focusOutEvent(self, event):
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        cursor = self.textCursor()
        cursor.clearSelection()
        self.setTextCursor(cursor)
        super().focusOutEvent(event)


class NoteTool:
    def __init__(self, view):
        self.view = view
        self.text_notes = []
        self.note_color = Qt.GlobalColor.blue

    def on_press(self, pos, scene, scale):
        self.add_text_note(pos, scene)

    def on_move(self, pos, scene, scale):
        pass

    def on_release(self, pos, scene, scale):
        pass

    def add_text_note(self, pos, scene):
        text, ok = QtWidgets.QInputDialog.getText(self.view, 'Добавить заметку', 'Введите текст заметки:')
        if ok and text.strip():
            note_item = TextNoteItem(text.strip(), color=self.note_color)
            note_item.setPos(pos)
            scene.addItem(note_item)
            self.text_notes.append(note_item)
            self.view.undo_stack.push(GraphicsItemCommand(scene, note_item, self.text_notes))
            return note_item
        return None

    def clear_all(self, scene):
        for item in list(self.text_notes):
            if item and item.scene() == scene:
                scene.removeItem(item)
        self.text_notes.clear()
