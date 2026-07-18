import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtWidgets

from ui.main_window import DICOMViewer
from ui.sidebar import SidebarWidget, ThumbnailWidget


class SidebarFullListTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_folder_load_keeps_first_four_files_in_sidebar_catalogue(self):
        window = DICOMViewer(settings=False)
        window.show()
        paths = [f"C:/study/image_{index:03d}.dcm" for index in range(9)]
        queued_for_views = []
        window._load_files_into_views = lambda files: queued_for_views.extend(files)

        with mock.patch.object(window.sidebar, "update_sidebar"):
            window.load_files(paths)
            self.app.processEvents()

        self.assertEqual(window.sidebar.extra_files, paths)
        self.assertEqual(queued_for_views, paths[:4])
        self.assertEqual(window.current_mode_index, 2)
        window.close()

    def test_sidebar_builds_more_than_old_two_hundred_item_limit(self):
        sidebar = SidebarWidget()
        sidebar.extra_files = [f"C:/study/image_{index:03d}.dcm" for index in range(205)]

        with mock.patch.object(ThumbnailWidget, "load_thumbnail", lambda _self: None):
            sidebar.update_sidebar()

        thumbnails = sidebar.findChildren(ThumbnailWidget)
        self.assertEqual(len(thumbnails), 205)
        self.assertEqual(sidebar.count_label.text(), "205 files")
        sidebar.deleteLater()

    def test_sidebar_drop_does_not_remove_active_file_from_catalogue(self):
        window = DICOMViewer(settings=False)
        study_files = ["C:/study/a.dcm", "C:/study/b.dcm"]
        window.sidebar.extra_files = list(study_files)
        callbacks = []
        window._start_file_load = lambda path, index, on_success=None, **_kwargs: callbacks.append(
            (path, index, on_success)
        )

        window._handle_sidebar_drop(0, study_files[1])
        callbacks[0][2](0, None)

        self.assertEqual(window.sidebar.extra_files, study_files)
        window.close()


if __name__ == "__main__":
    unittest.main()
