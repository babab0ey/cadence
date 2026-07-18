import tempfile
import unittest
from pathlib import Path

import numpy as np
import pydicom

from core.image_loader import load_dicom_file
from core.utils import fix_dicom_encoding
from tests.test_safe_loader import write_dicom


class DicomEncodingTests(unittest.TestCase):
    def test_valid_latin_diacritics_are_not_redecoded(self):
        for value in ("Müller^Élodie", "José", "Ångström", "François^Noël"):
            with self.subTest(value=value):
                self.assertEqual(fix_dicom_encoding(value), value)

    def test_already_decoded_cyrillic_is_unchanged(self):
        value = "Иванов^Мария"
        self.assertEqual(fix_dicom_encoding(value), value)

    def test_high_confidence_cp1251_mojibake_is_repaired(self):
        original = "Иванов^Мария"
        mojibake = original.encode("cp1251").decode("latin1")
        self.assertEqual(fix_dicom_encoding(mojibake), original)

    def test_short_or_ambiguous_text_is_unchanged(self):
        value = "Éva^Öz"
        self.assertEqual(fix_dicom_encoding(value), value)

    def test_declared_dicom_charset_disables_heuristic(self):
        original = "Иванов^Мария"
        mojibake = original.encode("cp1251").decode("latin1")
        self.assertEqual(fix_dicom_encoding(mojibake, "ISO_IR 100"), mojibake)

    def test_loader_preserves_utf8_patient_name_with_diacritics(self):
        with tempfile.TemporaryDirectory(prefix="dicom-encoding-") as directory:
            path = Path(directory) / "latin-name.dcm"
            write_dicom(path, np.arange(64, dtype=np.uint16).reshape(8, 8))
            dataset = pydicom.dcmread(str(path))
            dataset.PatientName = "Müller^Élodie"
            dataset.PatientID = "José-01"
            dataset.save_as(str(path))

            view_data = load_dicom_file(str(path))

            self.assertEqual(view_data.patient_name, "Müller^Élodie")
            self.assertEqual(view_data.patient_id, "José-01")


if __name__ == "__main__":
    unittest.main()
