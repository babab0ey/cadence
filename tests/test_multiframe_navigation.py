import os
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PyQt6 import QtCore, QtGui, QtWidgets

from tests.test_safe_loader import write_dicom
from ui.main_window import DICOMViewer
from ui.viewport import InteractiveGraphicsView


class MultiframeNavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_controls_only_appear_for_multiframe_images(self):
        scene = QtWidgets.QGraphicsScene()
        view = InteractiveGraphicsView(scene)
        view.resize(500, 320)
        view.show()

        view.set_frame_navigation(0, 1)
        self.assertFalse(view._frame_controls.isVisible())

        view.set_frame_navigation(2, 47)
        self.app.processEvents()
        self.assertTrue(view._frame_controls.isVisible())
        self.assertEqual(view._frame_label.text(), "Кадр 3 / 47")
        self.assertEqual(view._frame_slider.minimum(), 0)
        self.assertEqual(view._frame_slider.maximum(), 46)
        view.close()

    def test_alt_wheel_changes_frame_without_zooming(self):
        scene = QtWidgets.QGraphicsScene()
        view = InteractiveGraphicsView(scene)
        view.set_frame_navigation(1, 4)
        requested = []
        view.frameChangeRequested.connect(lambda _view, frame: requested.append(frame))
        scale_before = view.transform().m11()
        event = QtGui.QWheelEvent(
            QtCore.QPointF(30, 30),
            QtCore.QPointF(30, 30),
            QtCore.QPoint(0, 0),
            QtCore.QPoint(0, 120),
            QtCore.Qt.MouseButton.NoButton,
            QtCore.Qt.KeyboardModifier.AltModifier,
            QtCore.Qt.ScrollPhase.ScrollUpdate,
            False,
        )

        view.wheelEvent(event)

        self.assertEqual(requested, [2])
        self.assertEqual(view.transform().m11(), scale_before)

    def test_async_frame_change_preserves_window_level_and_view_transform(self):
        with tempfile.TemporaryDirectory(prefix="multiframe viewer ") as temp_dir:
            path = Path(temp_dir) / "three-frames.dcm"
            frames = np.stack(
                [
                    np.full((32, 40), 10, dtype=np.uint16),
                    np.full((32, 40), 20, dtype=np.uint16),
                    np.full((32, 40), 30, dtype=np.uint16),
                ]
            )
            write_dicom(path, frames, number_of_frames=3)
            window = DICOMViewer(settings=False)
            window.show()
            self.assertTrue(window._load_generic_file(str(path), 0))
            view = window.all_views[0]
            data = window.view_data[0]
            data.wc = 111.0
            data.ww = 222.0
            data.rotation = 90
            window._apply_item_transformations(0)
            view.scale(1.4, 1.4)
            transform_before = QtGui.QTransform(view.transform())

            window._on_frame_change_requested(view, 1)
            deadline = time.monotonic() + 10
            while window._pending_loads and time.monotonic() < deadline:
                self.app.processEvents()
                time.sleep(0.005)
            self.app.processEvents()

            changed = window.view_data[0]
            self.assertFalse(window._pending_loads)
            self.assertEqual(changed.current_frame_index, 1)
            self.assertEqual(changed.number_of_frames, 3)
            self.assertTrue(np.all(changed.original_array == 20))
            self.assertEqual((changed.wc, changed.ww), (111.0, 222.0))
            self.assertEqual(changed.rotation, 90)
            self.assertEqual(view.transform(), transform_before)
            self.assertEqual(view._frame_label.text(), "Кадр 2 / 3")
            self.assertTrue(view._frame_controls.isVisible())
            window.close()


if __name__ == "__main__":
    unittest.main()
