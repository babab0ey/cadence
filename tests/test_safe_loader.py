import logging
import tempfile
import unittest
from logging.handlers import RotatingFileHandler
from pathlib import Path

import numpy as np
import pydicom
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

from core.errors import (
    CorruptFileError,
    InvalidMetadataError,
    MissingCodecError,
    UnsupportedFormatError,
)
from core.image_loader import (
    _classify_dicom_decode_error,
    apply_adjustments_pipeline,
    load_dicom_file,
    load_generic_file,
    load_thumbnail_qimage,
)
from core.logging_config import BACKUP_COUNT, MAX_LOG_BYTES, LOGGER_NAME, setup_logging
from core.tasks import FileLoadTask


def write_dicom(path: Path, array: np.ndarray, *, transfer_syntax=True, number_of_frames=None):
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = generate_uid()
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.ImplementationClassUID = generate_uid()
    if transfer_syntax:
        meta.TransferSyntaxUID = ExplicitVRLittleEndian

    dataset = FileDataset(str(path), {}, file_meta=meta, preamble=b"\0" * 128)
    dataset.SOPClassUID = meta.MediaStorageSOPClassUID
    dataset.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
    dataset.PatientName = "Тестовый^Пациент"
    dataset.PatientID = "TEST-01"
    dataset.SpecificCharacterSet = "ISO_IR 192"
    dataset.Modality = "MG"
    if number_of_frames is not None:
        dataset.NumberOfFrames = str(number_of_frames)
        rows, columns = array.shape[-2:]
    else:
        rows, columns = array.shape[:2]
    dataset.Rows = rows
    dataset.Columns = columns
    dataset.SamplesPerPixel = 1
    dataset.PhotometricInterpretation = "MONOCHROME2"
    dataset.BitsAllocated = 16
    dataset.BitsStored = 12
    dataset.HighBit = 11
    dataset.PixelRepresentation = 0
    dataset.WindowCenter = 2048
    dataset.WindowWidth = 4096
    dataset.PixelData = np.ascontiguousarray(array).tobytes()
    pydicom.dcmwrite(str(path), dataset, enforce_file_format=False)


class SafeLoaderTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="dicom viewer кириллица ")
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_cyrillic_and_spaced_path_loads_without_float64_copy(self):
        path = self.root / "снимок пациента 01.dcm"
        source = np.arange(64, dtype=np.uint16).reshape(8, 8)
        write_dicom(path, source)

        view_data = load_generic_file(str(path))
        apply_adjustments_pipeline(view_data)

        np.testing.assert_array_equal(view_data.original_array, source)
        self.assertEqual(view_data.original_array.dtype, np.uint16)
        self.assertIsNone(view_data.rescaled_array)
        self.assertEqual(view_data.base_8bit_array.dtype, np.uint8)
        self.assertIs(view_data.adjusted_array, view_data.base_8bit_array)
        self.assertFalse(view_data.qimage.isNull())

    def test_multiframe_loader_decodes_only_selected_frame(self):
        path = self.root / "multiframe.dcm"
        source = np.stack(
            [
                np.full((7, 9), 10, dtype=np.uint16),
                np.full((7, 9), 20, dtype=np.uint16),
                np.full((7, 9), 30, dtype=np.uint16),
            ]
        )
        write_dicom(path, source, number_of_frames=3)

        view_data = load_dicom_file(str(path), frame_index=1)

        self.assertEqual(view_data.number_of_frames, 3)
        self.assertEqual(view_data.current_frame_index, 1)
        self.assertEqual(view_data.original_array.shape, (7, 9))
        self.assertTrue(np.all(view_data.original_array == 20))

    def test_missing_transfer_syntax_is_metadata_error_not_attribute_error(self):
        path = self.root / "missing-transfer-syntax.dcm"
        write_dicom(path, np.zeros((4, 4), dtype=np.uint16), transfer_syntax=False)

        with self.assertRaises(InvalidMetadataError) as caught:
            load_dicom_file(str(path))

        self.assertEqual(caught.exception.code, "invalid_metadata")
        self.assertIn("TransferSyntaxUID", caught.exception.detail)

    def test_corrupt_file_has_a_specific_safe_error(self):
        path = self.root / "damaged.dcm"
        path.write_bytes(b"this is not a dicom file")

        with self.assertRaises(CorruptFileError) as caught:
            load_dicom_file(str(path))

        self.assertEqual(caught.exception.code, "corrupt_file")
        self.assertIn("повреждён", caught.exception.user_message)

    def test_missing_codec_and_unsupported_format_are_distinct(self):
        dataset = pydicom.Dataset()
        dataset.file_meta = FileMetaDataset()
        dataset.file_meta.TransferSyntaxUID = "1.2.840.10008.1.2.4.90"
        codec_error = _classify_dicom_decode_error(
            RuntimeError("decoder plugins are missing dependencies: pylibjpeg"),
            str(self.root / "compressed.dcm"),
            dataset,
        )
        dicom_unsupported = _classify_dicom_decode_error(
            NotImplementedError("No pixel data decoders have been implemented for this transfer syntax"),
            str(self.root / "unknown-syntax.dcm"),
            dataset,
        )
        unsupported = self.root / "notes.txt"
        unsupported.write_text("not an image", encoding="utf-8")

        self.assertIsInstance(codec_error, MissingCodecError)
        self.assertIsInstance(dicom_unsupported, UnsupportedFormatError)
        with self.assertRaises(UnsupportedFormatError):
            load_generic_file(str(unsupported))

    def test_thumbnail_is_small_and_owns_only_preview_buffer(self):
        path = self.root / "large.dcm"
        write_dicom(path, np.arange(512 * 384, dtype=np.uint16).reshape(512, 384))

        thumbnail = load_thumbnail_qimage(str(path), max_size=168)

        self.assertFalse(thumbnail.isNull())
        self.assertLessEqual(thumbnail.width(), 168)
        self.assertLessEqual(thumbnail.height(), 168)

    def test_background_task_returns_processed_view_data(self):
        path = self.root / "background.dcm"
        write_dicom(path, np.arange(100, dtype=np.uint16).reshape(10, 10))
        succeeded = []
        failed = []
        task = FileLoadTask(42, str(path))
        task.signals.succeeded.connect(lambda token, data: succeeded.append((token, data)))
        task.signals.failed.connect(lambda token, error: failed.append((token, error)))

        task.run()

        self.assertFalse(failed)
        self.assertEqual(succeeded[0][0], 42)
        self.assertIsNotNone(succeeded[0][1].base_8bit_array)

    def test_rotating_log_configuration_is_bounded(self):
        log_path = setup_logging()
        handlers = logging.getLogger(LOGGER_NAME).handlers
        rotating = [item for item in handlers if isinstance(item, RotatingFileHandler)]

        self.assertTrue(log_path.parent.exists())
        self.assertEqual(len(rotating), 1)
        self.assertEqual(rotating[0].maxBytes, MAX_LOG_BYTES)
        self.assertEqual(rotating[0].backupCount, BACKUP_COUNT)


if __name__ == "__main__":
    unittest.main()
