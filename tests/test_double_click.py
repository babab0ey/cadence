import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PyQt6 import QtCore, QtGui, QtWidgets

from models.view_data import ViewData
from ui.main_window import DICOMViewer
from ui.viewport import InteractiveGraphicsView


def left_mouse_event(event_type, position=QtCore.QPoint(24, 24)):
    point = QtCore.QPointF(position)
    return QtGui.QMouseEvent(
        event_type,
        point,
        point,
        point,
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
    )


class DoubleClickTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def make_loaded_view(self):
        scene = QtWidgets.QGraphicsScene()
        view = InteractiveGraphicsView(scene)
        pixmap = QtGui.QPixmap(64, 64)
        pixmap.fill(QtGui.QColor("gray"))
        item = scene.addPixmap(pixmap)
        view.set_image_data(np.zeros((64, 64), dtype=np.uint8), 1.0, item)
        return view

    def test_single_click_only_activates_view(self):
        view = self.make_loaded_view()
        activated = []
        toggled = []
        view.viewClicked.connect(lambda selected: activated.append(selected))
        view.singleViewToggleRequested.connect(lambda selected: toggled.append(selected))

        view.mousePressEvent(left_mouse_event(QtCore.QEvent.Type.MouseButtonPress))

        self.assertEqual(activated, [view])
        self.assertFalse(toggled)

    def test_double_click_on_image_only_requests_single_view(self):
        view = self.make_loaded_view()
        toggled = []
        load_requests = []
        view.singleViewToggleRequested.connect(lambda selected: toggled.append(selected))
        view.loadImageRequested.connect(lambda selected: load_requests.append(selected))

        view.mouseDoubleClickEvent(left_mouse_event(QtCore.QEvent.Type.MouseButtonDblClick))

        self.assertEqual(toggled, [view])
        self.assertFalse(load_requests)
        self.assertFalse(hasattr(view, "folderOpenRequested"))

    def test_double_click_toggles_focus_and_restores_previous_layout(self):
        window = DICOMViewer(settings=False)
        window.show()
        window._setup_layout_for_mode(2)
        data = ViewData(original_array=np.zeros((16, 16), dtype=np.uint16))
        window.view_data[1] = data
        pixmap = QtGui.QPixmap(16, 16)
        pixmap.fill(QtGui.QColor("gray"))
        item = window.all_scenes[1].addPixmap(pixmap)
        data.pixmap_item = item
        window.all_views[1].set_image_data(np.zeros((16, 16), dtype=np.uint8), 1.0, item)

        window.all_views[1].mouseDoubleClickEvent(
            left_mouse_event(QtCore.QEvent.Type.MouseButtonDblClick)
        )
        self.app.processEvents()
        self.assertTrue(window.focus_mode)
        self.assertEqual(window._focus_view_index, 1)

        window.all_views[1].mouseDoubleClickEvent(
            left_mouse_event(QtCore.QEvent.Type.MouseButtonDblClick)
        )
        self.app.processEvents()
        self.assertFalse(window.focus_mode)
        self.assertEqual([view.isVisible() for view in window.all_views], [True, True, True, True])
        window.close()


if __name__ == "__main__":
    unittest.main()
