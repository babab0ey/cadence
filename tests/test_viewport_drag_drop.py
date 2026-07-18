import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PyQt6 import QtCore, QtGui, QtWidgets

from core.utils import convert_numpy_to_qimage
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
        self.window = DICOMViewer(settings=False)
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

    def _load_test_image(self, index, width, height, value):
        array = np.full((height, width), value, dtype=np.uint8)
        self.window.view_data[index] = ViewData(
            file_path=f"C:/study/rendered_{index}.dcm",
            original_array=array,
            base_8bit_array=array,
            adjusted_array=array,
            qimage=convert_numpy_to_qimage(array),
        )
        self.window._update_single_view_display(index)

    def test_rendered_swap_rebuilds_pixmaps_in_their_destination_scenes(self):
        self.window._setup_layout_for_mode(2)
        for index, (width, height) in enumerate(((120, 80), (70, 100), (200, 50), (90, 160))):
            self._load_test_image(index, width, height, 30 + index * 40)
        self.app.processEvents()

        source_view = self.window.all_views[0]
        source_view.scale(8.0, 8.0)
        path = QtGui.QPainterPath(QtCore.QPointF(10, 20))
        path.lineTo(30, 40)
        drawing = QtWidgets.QGraphicsPathItem(path)
        self.window.all_scenes[0].addItem(drawing)
        source_view.pen_items.append(drawing)
        source_view._register_current_annotations()

        self.window.swap_view_data(0, 2)
        self.app.processEvents()

        self.assertEqual(self.window.view_data[2].file_path, "C:/study/rendered_0.dcm")
        self.assertEqual(self.window.view_data[0].file_path, "C:/study/rendered_2.dcm")
        for index in range(4):
            self.assertIs(self.window.view_data[index].pixmap_item.scene(), self.window.all_scenes[index])
        self.assertIs(drawing.scene(), self.window.all_scenes[2])
        self.assertIn(drawing, self.window.all_views[2].pen_items)
        self.assertLess(self.window.all_views[2].transform().m11(), 8.0)

    def test_annotations_follow_flip_rotation_and_reset(self):
        self.window._setup_layout_for_mode(0)
        self._load_test_image(0, 120, 80, 90)
        view = self.window.all_views[0]
        image_item = self.window.view_data[0].pixmap_item
        anchor = QtCore.QPointF(10, 20)
        path = QtGui.QPainterPath(anchor)
        path.lineTo(30, 40)
        drawing = QtWidgets.QGraphicsPathItem(path)
        self.window.all_scenes[0].addItem(drawing)
        view.pen_items.append(drawing)
        view._register_current_annotations()

        def assert_glued_to_image():
            expected = image_item.sceneTransform().map(anchor)
            actual = drawing.mapToScene(anchor)
            self.assertAlmostEqual(actual.x(), expected.x(), places=5)
            self.assertAlmostEqual(actual.y(), expected.y(), places=5)

        assert_glued_to_image()
        self.window.flip_horizontal()
        assert_glued_to_image()
        self.window.flip_vertical()
        assert_glued_to_image()
        self.window.rotate_image()
        assert_glued_to_image()
        self.window.reset_view()
        assert_glued_to_image()

    def test_erase_annotations_clears_every_view_but_keeps_images(self):
        self.window._setup_layout_for_mode(2)
        drawings = []
        for index in range(4):
            self._load_test_image(index, 64, 64, 30 + index)
            path = QtGui.QPainterPath(QtCore.QPointF(4, 4))
            path.lineTo(20, 20)
            drawing = QtWidgets.QGraphicsPathItem(path)
            self.window.all_scenes[index].addItem(drawing)
            self.window.all_views[index].pen_items.append(drawing)
            drawings.append(drawing)
        self.window._notify = lambda *_args, **_kwargs: None

        self.window.clear_interactive_overlays()

        for index, drawing in enumerate(drawings):
            self.assertIsNone(drawing.scene())
            self.assertEqual(self.window.all_views[index].pen_items, [])
            self.assertIsNotNone(self.window.view_data[index].pixmap_item)

    def test_clear_study_unloads_sidebar_and_all_viewports_only_in_app(self):
        self.window._setup_layout_for_mode(2)
        paths = []
        for index in range(4):
            self._load_test_image(index, 64, 64, 60 + index)
            paths.append(self.window.view_data[index].file_path)
        self.window.sidebar.extra_files = list(paths)

        self.window.clear_all_views_data()

        self.assertEqual(self.window.sidebar.extra_files, [])
        self.assertTrue(all(view_data.file_path is None for view_data in self.window.view_data))
        self.assertTrue(all(view.pixmap_item_ref is None for view in self.window.all_views))


if __name__ == "__main__":
    unittest.main()
