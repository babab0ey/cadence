import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PyQt6 import QtCore, QtGui, QtWidgets

from models.view_data import ViewData
from ui.main_window import DICOMViewer
from ui.viewport import InteractiveGraphicsView


def mouse_event(event_type, position, button, buttons, modifiers=QtCore.Qt.KeyboardModifier.NoModifier):
    point = QtCore.QPointF(position)
    return QtGui.QMouseEvent(event_type, point, point, point, button, buttons, modifiers)


class MouseGestureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def make_view(self):
        scene = QtWidgets.QGraphicsScene()
        view = InteractiveGraphicsView(scene)
        pixmap = QtGui.QPixmap(64, 64)
        pixmap.fill(QtGui.QColor("gray"))
        item = scene.addPixmap(pixmap)
        view.set_image_data(np.zeros((64, 64), dtype=np.uint8), 1.0, item)
        view.resize(320, 240)
        view.show()
        self.app.processEvents()
        return view

    def test_right_drag_is_window_level_not_pan(self):
        view = self.make_view()
        changes = []
        view.windowLevelChanged.connect(lambda _view, dx, dy: changes.append((dx, dy)))

        view.mousePressEvent(
            mouse_event(
                QtCore.QEvent.Type.MouseButtonPress,
                QtCore.QPoint(20, 20),
                QtCore.Qt.MouseButton.RightButton,
                QtCore.Qt.MouseButton.RightButton,
            )
        )
        view.mouseMoveEvent(
            mouse_event(
                QtCore.QEvent.Type.MouseMove,
                QtCore.QPoint(45, 5),
                QtCore.Qt.MouseButton.NoButton,
                QtCore.Qt.MouseButton.RightButton,
            )
        )

        self.assertTrue(view._is_window_leveling)
        self.assertFalse(view._is_panning)
        self.assertEqual(changes[-1], (25, -15))

        view.mouseReleaseEvent(
            mouse_event(
                QtCore.QEvent.Type.MouseButtonRelease,
                QtCore.QPoint(45, 5),
                QtCore.Qt.MouseButton.RightButton,
                QtCore.Qt.MouseButton.NoButton,
            )
        )
        self.assertFalse(view._is_window_leveling)
        view.close()

    def test_middle_and_shift_left_start_pan(self):
        for button, modifiers in (
            (QtCore.Qt.MouseButton.MiddleButton, QtCore.Qt.KeyboardModifier.NoModifier),
            (QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.ShiftModifier),
        ):
            view = self.make_view()
            view.mousePressEvent(
                mouse_event(
                    QtCore.QEvent.Type.MouseButtonPress,
                    QtCore.QPoint(30, 30),
                    button,
                    button,
                    modifiers,
                )
            )
            self.assertTrue(view._is_panning)
            self.assertEqual(view._pan_button, button)
            view.mouseReleaseEvent(
                mouse_event(
                    QtCore.QEvent.Type.MouseButtonRelease,
                    QtCore.QPoint(30, 30),
                    button,
                    QtCore.Qt.MouseButton.NoButton,
                    modifiers,
                )
            )
            self.assertFalse(view._is_panning)
            view.close()

    def test_window_level_mapping_updates_only_active_view(self):
        window = DICOMViewer()
        window.show()
        data = ViewData(
            original_array=np.arange(32 * 32, dtype=np.uint16).reshape(32, 32),
            wc=500.0,
            ww=1000.0,
        )
        window.view_data[0] = data
        view = window.all_views[0]

        window._on_window_level_started(view)
        window._on_window_level_changed(view, 30, -20)

        self.assertGreater(data.ww, 1000.0)
        self.assertLess(data.wc, 500.0)
        self.assertIsNone(window.view_data[1].wc)

        window._on_window_level_finished(view)
        self.assertIsNotNone(data.base_8bit_array)
        window.close()
        self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
