import os
import sys
import threading
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtWidgets

from core import logging_config
from ui.viewport import InteractiveGraphicsView


class ViewportSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_clearing_a_new_viewport_is_safe(self):
        scene = QtWidgets.QGraphicsScene()
        view = InteractiveGraphicsView(scene)

        view.clear_image_data()
        view.clear_all_drawing_items()

        self.assertIsNone(view.image_array_ref)
        self.assertEqual(len(scene.items()), 0)
        view.deleteLater()

    def test_global_exception_hooks_have_a_main_thread_dialog_bridge(self):
        previous_sys_hook = sys.excepthook
        previous_thread_hook = threading.excepthook
        try:
            logging_config.install_exception_hooks()

            self.assertIsNotNone(logging_config._dialog_bridge)
            self.assertIsNot(sys.excepthook, previous_sys_hook)
            self.assertIsNot(threading.excepthook, previous_thread_hook)
        finally:
            sys.excepthook = previous_sys_hook
            threading.excepthook = previous_thread_hook


if __name__ == "__main__":
    unittest.main()
