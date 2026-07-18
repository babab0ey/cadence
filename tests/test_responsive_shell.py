import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtCore, QtTest, QtWidgets

from ui.main_window import DICOMViewer
from ui.top_toolbar import PERMANENT_PRIMARY_ORDER


class ResponsiveShellTests(unittest.TestCase):
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

    def _resize(self, width, height):
        self.window.resize(width, height)
        self.app.processEvents()
        self.window.toolbar._update_responsive_state()

    def test_patient_info_is_first_and_primary_actions_never_overflow(self):
        self.assertEqual(PERMANENT_PRIMARY_ORDER[0], "info")
        for width, height in ((1920, 1080), (1366, 768), (1280, 720), (900, 600)):
            self._resize(width, height)
            buttons = self.window.toolbar._primary_buttons
            self.assertTrue(all(buttons[action_id].isVisible() for action_id in PERMANENT_PRIMARY_ORDER))
            positions = [self.window.toolbar._layout.indexOf(buttons[action_id]) for action_id in PERMANENT_PRIMARY_ORDER]
            self.assertEqual(positions, sorted(positions))
            self.assertEqual(positions[0], 0)

    def test_secondary_actions_move_to_more_and_return(self):
        self._resize(1366, 768)
        self.assertTrue(all(not button.isVisible() for _spec, _action, button in self.window.toolbar._secondary_buttons))
        self.assertTrue(self.window.toolbar.more_button.isVisible())

        self._resize(1920, 1080)
        self.assertTrue(any(button.isVisible() for _spec, _action, button in self.window.toolbar._secondary_buttons))

        self._resize(1280, 720)
        self.assertTrue(all(not button.isVisible() for _spec, _action, button in self.window.toolbar._secondary_buttons))
        self._resize(1920, 1080)
        self.assertTrue(any(button.isVisible() for _spec, _action, button in self.window.toolbar._secondary_buttons))

    def test_window_minimum_and_sidebar_compact_state(self):
        self.assertGreaterEqual(self.window.minimumWidth(), 900)
        self.assertGreaterEqual(self.window.minimumHeight(), 600)
        self.window.sidebar.set_collapsed(True, animate=False)
        self.assertEqual(self.window.sidebar.width(), 48)
        self.assertFalse(self.window.sidebar.search_bar.isVisible())
        self.assertTrue(self.window.sidebar.toggle_button.isVisible())
        self.window.sidebar.set_collapsed(False, animate=False)
        self.assertGreaterEqual(self.window.sidebar.minimumWidth(), 180)
        self.assertLessEqual(self.window.sidebar.maximumWidth(), 360)

    def test_sidebar_collapsed_state_persists(self):
        self.window.close()
        with tempfile.TemporaryDirectory(prefix="responsive settings ") as temp_dir:
            path = Path(temp_dir) / "viewer.ini"
            settings = QtCore.QSettings(str(path), QtCore.QSettings.Format.IniFormat)
            first = DICOMViewer(settings=settings)
            first.sidebar.restore_state(332, collapsed=True)
            first._save_settings()
            first.close()
            restored = DICOMViewer(settings=QtCore.QSettings(str(path), QtCore.QSettings.Format.IniFormat))
            self.assertTrue(restored.sidebar.is_collapsed)
            self.assertEqual(restored.sidebar.expanded_width, 332)
            restored.close()

    def test_skeleton_shimmer_fades_after_loading(self):
        view = self.window.all_views[0]
        view.set_loading(True)
        self.assertTrue(view._loading_overlay.isVisible())
        self.assertEqual(view._loading_overlay._shimmer.duration(), 1500)
        view.set_loading(False)
        QtTest.QTest.qWait(190)
        self.assertFalse(view._loading_overlay.isVisible())


if __name__ == "__main__":
    unittest.main()
