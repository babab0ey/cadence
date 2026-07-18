import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtWidgets

from ui.main_window import DICOMViewer


class FocusModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        self.window = DICOMViewer(settings=False)
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        if self.window.focus_mode or self.window._system_fullscreen_active:
            self.window._exit_single_view_mode()
        self.window.close()
        self.app.processEvents()

    def test_single_view_focus_keeps_info_visible_and_restores_quad_layout(self):
        self.window._setup_layout_for_mode(2)

        self.window._enter_single_view_mode(2)
        self.app.processEvents()

        self.assertTrue(self.window.focus_mode)
        self.assertEqual([view.isVisible() for view in self.window.all_views], [False, False, True, False])
        self.assertFalse(self.window.sidebar.isVisible())
        self.assertFalse(self.window.toolbar.isVisible())
        self.assertTrue(self.window.focus_controls.isVisible())
        self.assertTrue(self.window.focus_info_button.isVisible())

        self.window._exit_single_view_mode()
        self.app.processEvents()

        self.assertFalse(self.window.focus_mode)
        self.assertEqual([view.isVisible() for view in self.window.all_views], [True, True, True, True])
        self.assertTrue(self.window.sidebar.isVisible())
        self.assertTrue(self.window.toolbar.isVisible())

    def test_f11_uses_system_fullscreen_and_keeps_info_control(self):
        self.window._toggle_system_fullscreen()
        self.app.processEvents()

        self.assertTrue(self.window._system_fullscreen_active)
        self.assertTrue(self.window.focus_mode)
        self.assertTrue(self.window.focus_info_button.isVisible())

        self.window._toggle_system_fullscreen()
        self.app.processEvents()

        self.assertFalse(self.window._system_fullscreen_active)
        self.assertFalse(self.window.focus_mode)

    def test_escape_exits_focus_mode(self):
        self.window._setup_layout_for_mode(1)
        self.window._enter_single_view_mode(1)

        self.window._handle_escape()
        self.app.processEvents()

        self.assertFalse(self.window.focus_mode)
        self.assertEqual([view.isVisible() for view in self.window.all_views], [True, True, False, False])


if __name__ == "__main__":
    unittest.main()
