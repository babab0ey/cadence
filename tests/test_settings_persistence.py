import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtCore, QtWidgets

from ui.main_window import DICOMViewer


class SettingsPersistenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_required_settings_survive_restart(self):
        with tempfile.TemporaryDirectory(prefix="dicom settings ") as temp_dir:
            settings_path = Path(temp_dir) / "viewer.ini"
            study_folder = str(Path(temp_dir) / "исследование")
            Path(study_folder).mkdir()
            first_settings = QtCore.QSettings(
                str(settings_path), QtCore.QSettings.Format.IniFormat
            )
            first = DICOMViewer(settings=first_settings)
            first.resize(700, 550)
            first.move(40, 50)
            first.sidebar.setFixedWidth(252)
            first.last_opened_folder = study_folder
            first._setup_layout_for_mode(2)
            first.toolbar.set_current_mode(2)
            first.toggle_theme()
            expected_geometry = first.saveGeometry()
            first._save_settings()
            first.close()
            self.app.processEvents()

            restored_settings = QtCore.QSettings(
                str(settings_path), QtCore.QSettings.Format.IniFormat
            )
            restored = DICOMViewer(settings=restored_settings)

            self.assertTrue(restored.is_dark_theme)
            self.assertEqual(restored.last_opened_folder, study_folder)
            self.assertEqual(restored.current_mode_index, 2)
            self.assertTrue(restored.toolbar.mode_actions[2].isChecked())
            self.assertEqual(restored.sidebar.width(), 252)
            self.assertEqual(restored.saveGeometry(), expected_geometry)
            self.assertEqual(restored._default_open_directory(), study_folder)
            restored.close()

    def test_corrupt_layout_and_sidebar_values_are_clamped(self):
        with tempfile.TemporaryDirectory(prefix="dicom settings ") as temp_dir:
            settings = QtCore.QSettings(
                str(Path(temp_dir) / "viewer.ini"),
                QtCore.QSettings.Format.IniFormat,
            )
            settings.setValue("view/layout_mode", 99)
            settings.setValue("sidebar/width", 9999)
            settings.sync()

            window = DICOMViewer(settings=settings)

            self.assertEqual(window.current_mode_index, 2)
            self.assertEqual(window.sidebar.expanded_width, 360)
            window.close()


if __name__ == "__main__":
    unittest.main()
