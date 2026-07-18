import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtCore, QtGui, QtWidgets

from models.view_data import ViewData
from ui.main_window import DICOMViewer


def drop_event(payload):
    mime = QtCore.QMimeData()
    mime.setText(payload)
    event = QtGui.QDropEvent(
        QtCore.QPointF(20, 20),
        QtCore.Qt.DropAction.MoveAction,
        mime,
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
    )
    event._mime_data_ref = mime
    return event


class ViewportDragDropTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        self.window = DICOMViewer()
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.app.processEvents()

    def assert_all_ordered_swaps(self, mode, visible_indices):
        self.window._setup_layout_for_mode(mode)
        for source in visible_indices:
            for target in visible_indices:
                if source == target:
                    continue
                self.window.view_data = [
                    ViewData(file_path=f"C:/study/image_{index}.dcm")
                    for index in range(4)
                ]
                source_path = self.window.view_data[source].file_path
                target_path = self.window.view_data[target].file_path
                event = drop_event(f"main_view_file_{source}_{source_path}")

                self.window.all_views[target].dropEvent(event)

                self.assertTrue(event.isAccepted(), (mode, source, target))
                self.assertEqual(self.window.view_data[target].file_path, source_path)
                self.assertEqual(self.window.view_data[source].file_path, target_path)

    def test_all_swaps_in_double_layout(self):
        self.assert_all_ordered_swaps(1, range(2))

    def test_all_swaps_in_quad_layout(self):
        self.assert_all_ordered_swaps(2, range(4))

    def test_drag_payload_reads_view_data_attribute(self):
        self.window.view_data[0] = ViewData(file_path="C:/study/patient_01.dcm")

        payload = self.window.all_views[0]._main_view_drag_payload()

        self.assertEqual(payload, "main_view_file_0_C:/study/patient_01.dcm")

    def test_stale_payload_is_rejected(self):
        self.window._setup_layout_for_mode(1)
        self.window.view_data[0] = ViewData(file_path="C:/study/current.dcm")
        event = drop_event("main_view_file_0_C:/study/stale.dcm")

        self.window.all_views[1].dropEvent(event)

        self.assertFalse(event.isAccepted())
        self.assertEqual(self.window.view_data[0].file_path, "C:/study/current.dcm")


if __name__ == "__main__":
    unittest.main()
