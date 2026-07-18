import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtWidgets

from models.view_data import ViewData
from resources.design_tokens import DARK, GEOMETRY, LIGHT, build_stylesheet
from ui.dialogs.info_dialog import DicomInfoDialog, PatientField
from ui.dialogs.settings_dialog import SettingsDialog
from ui.main_window import DICOMViewer


class DesignSystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_required_palette_and_accessible_geometry(self):
        self.assertEqual(LIGHT["bg_app"], "#FAF9F6")
        self.assertEqual(LIGHT["accent"], "#D97757")
        self.assertEqual(LIGHT["viewer_bg"], "#1A1918")
        self.assertEqual(DARK["bg_app"], "#1F1E1C")
        self.assertEqual(DARK["viewer_bg"], "#141312")
        self.assertEqual(GEOMETRY["font_base"], 15)
        self.assertEqual(GEOMETRY["hit_target"], 44)
        self.assertIn("font-size: 15px", build_stylesheet(False))

    def test_every_application_icon_button_has_a_tooltip(self):
        window = DICOMViewer(settings=False)
        missing = []
        for button in window.findChildren(QtWidgets.QAbstractButton):
            if button.text().strip() or button.toolTip().strip():
                continue
            if button.objectName() == "qt_toolbar_ext_button" or type(button).__name__ == "Indicator":
                continue
            missing.append(button.objectName() or type(button).__name__)
        self.assertEqual(missing, [])
        window.close()

    def test_patient_fields_and_copy_all_are_human_readable(self):
        vd = ViewData(
            file_path="study.dcm",
            patient_name="Иванова Мария",
            patient_id="12345",
            study_description="Маммография",
            series_description="Правая проекция",
        )
        dialog = DicomInfoDialog(0, vd, 1.0, 0, 1.0, False, False)
        fields = dialog.findChildren(PatientField)
        self.assertGreaterEqual(len(fields), 20)
        fields[0].copy_value()
        self.assertEqual(self.app.clipboard().text(), fields[0].value_text)
        dialog.copy_all()
        copied = self.app.clipboard().text()
        self.assertIn("Пациент", copied)
        self.assertIn("Иванова Мария", copied)
        self.assertIn("Оборудование", copied)
        dialog.close()

    def test_settings_offer_light_dark_and_auto(self):
        dialog = SettingsDialog({"theme_mode": "light", "dark_theme": False})
        self.assertEqual(set(dialog.theme_buttons), {"light", "dark", "auto"})
        self.assertEqual(dialog.sensitivity_slider.minimum(), 40)
        self.assertEqual(dialog.sensitivity_slider.maximum(), 200)
        dialog.close()


if __name__ == "__main__":
    unittest.main()
