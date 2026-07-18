import gc
import json
import os

import numpy as np
import pydicom
from pydicom.errors import InvalidDicomError

from core.errors import (
    CorruptFileError,
    FileAccessError,
    InvalidMetadataError,
    MemoryLimitError,
    MissingCodecError,
    ProcessingError,
    UnsupportedFormatError,
    ViewerError,
    wrap_unexpected_error,
)
from core.image_processor import (
    apply_brightness_contrast,
    apply_rescale_window,
    downsample_array,
    normalize_image,
)
from core.logging_config import get_logger
from core.utils import (
    DICOM_EXTS,
    IMAGE_EXTS,
    JSON_EXTS,
    PIL_AVAILABLE,
    convert_numpy_to_qimage,
    fix_dicom_encoding,
    format_dicom_date,
    format_dicom_time,
)
from models.view_data import ViewData


logger = get_logger("image_loader")

MAX_IMAGE_PIXELS = 100_000_000
PIXEL_DATA_TAGS = (0x7FE00010, 0x7FE00008, 0x7FE00009)


def _read_dicom_metadata(file_path):
    try:
        return pydicom.dcmread(file_path, defer_size=1024, force=False)
    except InvalidDicomError:
        try:
            dataset = pydicom.dcmread(file_path, defer_size=1024, force=True)
        except Exception as exc:
            raise CorruptFileError(file_path, f"{type(exc).__name__}: {exc}", exc) from exc
        if not dataset or not any(tag in dataset for tag in PIXEL_DATA_TAGS):
            raise CorruptFileError(file_path, "Файл не содержит корректной структуры DICOM")
        return dataset
    except (FileNotFoundError, PermissionError, OSError) as exc:
        raise FileAccessError(file_path, f"{type(exc).__name__}: {exc}", exc) from exc
    except Exception as exc:
        raise CorruptFileError(file_path, f"{type(exc).__name__}: {exc}", exc) from exc


def _get_transfer_syntax(dataset):
    file_meta = getattr(dataset, "file_meta", None)
    return getattr(file_meta, "TransferSyntaxUID", None) if file_meta is not None else None


def _has_pixel_data(dataset):
    return any(tag in dataset for tag in PIXEL_DATA_TAGS)


def _classify_dicom_decode_error(exc, file_path, dataset):
    if isinstance(exc, ViewerError):
        return exc
    if isinstance(exc, MemoryError):
        return MemoryLimitError(file_path, str(exc), exc)

    message = f"{type(exc).__name__}: {exc}"
    lowered = message.lower()
    transfer_syntax = _get_transfer_syntax(dataset)

    codec_markers = (
        "missing dependencies",
        "plugins are missing",
        "no suitable plugins",
        "unable to decompress",
        "decoder plugins",
        "requires gdcm",
        "requires pylibjpeg",
        "requires pyjpegls",
    )
    if any(marker in lowered for marker in codec_markers):
        detail = f"TransferSyntaxUID={transfer_syntax or 'отсутствует'}; {message}"
        return MissingCodecError(file_path, detail, exc)

    unsupported_markers = (
        "no pixel data decoders have been implemented",
        "unsupported transfer syntax",
        "not a transfer syntax",
        "pixel data decoder is not available",
    )
    if any(marker in lowered for marker in unsupported_markers):
        return UnsupportedFormatError(file_path, message, exc)

    metadata_markers = (
        "transfer syntax uid",
        "missing required element",
        "bits allocated",
        "bits stored",
        "samples per pixel",
        "photometric interpretation",
        "no pixel data",
        "pixel data element",
        "rows",
        "columns",
    )
    if any(marker in lowered for marker in metadata_markers):
        return InvalidMetadataError(file_path, message, exc)

    corrupt_markers = (
        "less than expected",
        "excess padding",
        "truncated",
        "unexpected tag",
        "misplaced marker",
        "invalid value for vr",
        "broken data stream",
        "cannot identify image",
        "decompression bomb",
    )
    if any(marker in lowered for marker in corrupt_markers):
        return CorruptFileError(file_path, message, exc)

    return CorruptFileError(file_path, message, exc)


def _decode_dicom_frame(file_path, dataset, frame_index=0):
    try:
        from pydicom.pixels import pixel_array as decode_pixel_array

        return decode_pixel_array(file_path, index=frame_index)
    except InvalidDicomError:
        # Rare legacy files without the DICOM preamble require force=True. This
        # fallback may read the raw PixelData, but still keeps only one frame.
        try:
            dataset.pixel_array_options(index=frame_index)
            decoded = dataset.pixel_array
            return np.array(decoded, copy=True)
        except Exception as exc:
            raise _classify_dicom_decode_error(exc, file_path, dataset) from exc
    except Exception as exc:
        raise _classify_dicom_decode_error(exc, file_path, dataset) from exc


def _first_value(value):
    if isinstance(value, pydicom.multival.MultiValue):
        return value[0] if value else None
    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    return value


def _safe_float(value, default, file_path, field_name):
    if value in (None, ""):
        return default
    try:
        return float(_first_value(value))
    except (TypeError, ValueError, OverflowError) as exc:
        raise InvalidMetadataError(
            file_path,
            f"Некорректное поле {field_name}: {value!r}",
            exc,
        ) from exc


def _validate_pixel_array(array, file_path):
    if array is None or array.size == 0:
        raise CorruptFileError(file_path, "Пиксельные данные пусты")
    if array.ndim not in (2, 3):
        raise UnsupportedFormatError(file_path, f"Неподдерживаемая форма массива: {array.shape}")
    height, width = array.shape[:2]
    if height <= 0 or width <= 0:
        raise InvalidMetadataError(file_path, f"Некорректный размер: {array.shape}")
    if height * width > MAX_IMAGE_PIXELS:
        raise MemoryLimitError(
            file_path,
            f"Размер {width}x{height} превышает безопасный предел {MAX_IMAGE_PIXELS} пикселей",
        )


def load_dicom_file(file_path, frame_index=0):
    dataset = _read_dicom_metadata(file_path)
    if not _has_pixel_data(dataset):
        raise InvalidMetadataError(file_path, "Файл не содержит пиксельных данных")

    transfer_syntax = _get_transfer_syntax(dataset)
    if transfer_syntax is None:
        raise InvalidMetadataError(file_path, "Отсутствует обязательный TransferSyntaxUID")

    try:
        number_of_frames = max(1, int(getattr(dataset, "NumberOfFrames", 1) or 1))
    except (TypeError, ValueError) as exc:
        raise InvalidMetadataError(file_path, "Некорректное NumberOfFrames", exc) from exc
    if not 0 <= int(frame_index) < number_of_frames:
        raise InvalidMetadataError(
            file_path,
            f"Кадр {frame_index + 1} отсутствует; всего кадров: {number_of_frames}",
        )

    logger.info(
        "Открытие DICOM: %s; TransferSyntaxUID=%s; frame=%s/%s",
        file_path,
        transfer_syntax,
        frame_index + 1,
        number_of_frames,
    )
    pixel_array = _decode_dicom_frame(file_path, dataset, frame_index)
    pixel_array = np.asarray(pixel_array)
    _validate_pixel_array(pixel_array, file_path)
    if not pixel_array.flags.c_contiguous:
        pixel_array = np.ascontiguousarray(pixel_array)

    view_data = ViewData()
    view_data.file_path = file_path
    view_data.original_array = pixel_array
    view_data.file_type = "dicom"
    view_data.photometric_interpretation = str(
        dataset.get("PhotometricInterpretation", "MONOCHROME2")
    )
    view_data.rescale_slope = _safe_float(dataset.get("RescaleSlope"), 1.0, file_path, "RescaleSlope")
    view_data.rescale_intercept = _safe_float(
        dataset.get("RescaleIntercept"), 0.0, file_path, "RescaleIntercept"
    )
    view_data.number_of_frames = number_of_frames
    view_data.current_frame_index = int(frame_index)

    wc_value = _first_value(dataset.get("WindowCenter"))
    ww_value = _first_value(dataset.get("WindowWidth"))
    if wc_value is None or ww_value is None:
        voi_lut_sequence = dataset.get("VOILUTSequence")
        if voi_lut_sequence:
            wc_value = _first_value(voi_lut_sequence[0].get("WindowCenter", wc_value))
            ww_value = _first_value(voi_lut_sequence[0].get("WindowWidth", ww_value))
    view_data.wc = _safe_float(wc_value, None, file_path, "WindowCenter")
    parsed_ww = _safe_float(ww_value, None, file_path, "WindowWidth")
    view_data.ww = parsed_ww if parsed_ww is not None and parsed_ww >= 1.0 else None

    spacing = dataset.get("PixelSpacing", dataset.get("ImagerPixelSpacing"))
    view_data.pixel_spacing = _safe_float(spacing, 1.0, file_path, "PixelSpacing")
    if view_data.pixel_spacing < 1e-9:
        view_data.pixel_spacing = 1.0

    specific_character_set = dataset.get("SpecificCharacterSet")
    view_data.patient_name = fix_dicom_encoding(
        str(dataset.get("PatientName", "N/A")), specific_character_set
    )
    view_data.patient_id = fix_dicom_encoding(
        str(dataset.get("PatientID", "N/A")), specific_character_set
    )
    view_data.patient_birth_date = format_dicom_date(str(dataset.get("PatientBirthDate", "")))
    view_data.patient_sex = str(dataset.get("PatientSex", "N/A"))
    view_data.study_date = format_dicom_date(str(dataset.get("StudyDate", "")))
    view_data.study_time = format_dicom_time(str(dataset.get("StudyTime", "")))
    view_data.study_description = fix_dicom_encoding(
        str(dataset.get("StudyDescription", "N/A")), specific_character_set
    )
    view_data.modality = str(dataset.get("Modality", "N/A"))
    view_data.institution_name = fix_dicom_encoding(
        str(dataset.get("InstitutionName", "N/A")), specific_character_set
    )
    view_data.body_part = fix_dicom_encoding(
        str(dataset.get("BodyPartExamined", "N/A")), specific_character_set
    )
    view_data.view_position = str(dataset.get("ViewPosition", ""))
    view_data.series_description = fix_dicom_encoding(
        str(dataset.get("SeriesDescription", "")), specific_character_set
    )
    view_data.manufacturer = fix_dicom_encoding(
        str(dataset.get("Manufacturer", "N/A")), specific_character_set
    )
    view_data.equipment_model = fix_dicom_encoding(
        str(dataset.get("ManufacturerModelName", "N/A")), specific_character_set
    )
    view_data.station_name = fix_dicom_encoding(
        str(dataset.get("StationName", "N/A")), specific_character_set
    )

    del dataset
    gc.collect()
    return view_data


def load_image_file(file_path):
    if not PIL_AVAILABLE:
        raise UnsupportedFormatError(file_path, "Для обычных изображений требуется Pillow")
    try:
        from PIL import Image as PILImage

        with PILImage.open(file_path) as image:
            # The Pillow object is closed at the end of this block, therefore the
            # NumPy buffer must own its memory.
            image_array = np.array(image.convert("L"), copy=True)
    except (FileNotFoundError, PermissionError, OSError) as exc:
        raise FileAccessError(file_path, f"{type(exc).__name__}: {exc}", exc) from exc
    except Exception as exc:
        raise CorruptFileError(file_path, f"{type(exc).__name__}: {exc}", exc) from exc

    view_data = ViewData()
    view_data.file_path = file_path
    view_data.original_array = image_array
    view_data.file_type = "image"
    view_data.photometric_interpretation = "MONOCHROME2"
    view_data.patient_name = os.path.basename(file_path)
    view_data.patient_id = "IMAGE"
    view_data.study_description = f"Изображение {os.path.splitext(file_path)[1].upper()}"
    view_data.modality = "IMG"
    return view_data


def load_json_file(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            data = json.load(file)
    except (FileNotFoundError, PermissionError, OSError) as exc:
        raise FileAccessError(file_path, f"{type(exc).__name__}: {exc}", exc) from exc
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise CorruptFileError(file_path, f"{type(exc).__name__}: {exc}", exc) from exc

    image_data = None
    if isinstance(data, dict):
        for key in ("image", "data", "array", "pixels", "pixel_data"):
            if key in data:
                image_data = data[key]
                break
        if image_data is None and all(isinstance(value, (list, int, float)) for value in data.values()):
            image_data = list(data.values())
    elif isinstance(data, list):
        image_data = data
    if image_data is None:
        raise UnsupportedFormatError(file_path, "В JSON не найдены данные изображения")

    try:
        image_array = np.asarray(image_data)
    except Exception as exc:
        raise CorruptFileError(file_path, f"Некорректный массив JSON: {exc}", exc) from exc
    if image_array.ndim < 2 or image_array.size == 0:
        raise UnsupportedFormatError(file_path, "JSON не содержит двумерного изображения")
    if image_array.ndim > 2:
        image_array = image_array[0]
    _validate_pixel_array(image_array, file_path)

    view_data = ViewData()
    view_data.file_path = file_path
    view_data.original_array = image_array
    view_data.file_type = "json"
    view_data.photometric_interpretation = "MONOCHROME2"
    view_data.patient_name = os.path.basename(file_path)
    view_data.patient_id = "JSON"
    return view_data


def load_generic_file(file_path, frame_index=0):
    if not file_path or not os.path.exists(file_path):
        raise FileAccessError(file_path, "Файл не найден")
    extension = os.path.splitext(file_path)[1].lower()
    try:
        if extension in DICOM_EXTS:
            return load_dicom_file(file_path, frame_index=frame_index)
        if extension in IMAGE_EXTS:
            return load_image_file(file_path)
        if extension in JSON_EXTS:
            return load_json_file(file_path)
        raise UnsupportedFormatError(file_path, f"Расширение {extension or 'отсутствует'}")
    except ViewerError:
        raise
    except BaseException as exc:
        raise wrap_unexpected_error(exc, file_path) from exc


def apply_adjustments_pipeline(view_data, brightness=0, contrast=1.0, negative=False):
    if view_data.original_array is None:
        view_data.rescaled_array = None
        view_data.base_8bit_array = None
        view_data.adjusted_array = None
        view_data.qimage = None
        return

    try:
        reusable_base = view_data.base_8bit_array
        view_data.base_8bit_array = apply_rescale_window(
            view_data.original_array,
            view_data.rescale_slope,
            view_data.rescale_intercept,
            view_data.wc,
            view_data.ww,
            view_data.photometric_interpretation,
            out=reusable_base,
        )
        view_data.rescaled_array = None

        reusable_adjusted = view_data.adjusted_array
        if reusable_adjusted is view_data.base_8bit_array:
            reusable_adjusted = None
        view_data.adjusted_array = apply_brightness_contrast(
            view_data.base_8bit_array,
            brightness,
            contrast,
            negative,
            out=reusable_adjusted if (brightness != 0 or contrast != 1.0 or negative) else None,
        )
        view_data.qimage = convert_numpy_to_qimage(view_data.adjusted_array)
    except MemoryError as exc:
        raise MemoryLimitError(view_data.file_path or "", str(exc), exc) from exc
    except ViewerError:
        raise
    except Exception as exc:
        raise ProcessingError(
            view_data.file_path or "",
            f"{type(exc).__name__}: {exc}",
            exc,
        ) from exc
    finally:
        gc.collect()


def update_brightness_contrast_only(view_data, brightness=0, contrast=1.0, negative=False):
    if view_data.base_8bit_array is None:
        return
    reusable = view_data.adjusted_array
    if reusable is view_data.base_8bit_array:
        reusable = None
    view_data.adjusted_array = apply_brightness_contrast(
        view_data.base_8bit_array,
        brightness,
        contrast,
        negative,
        out=reusable if (brightness != 0 or contrast != 1.0 or negative) else None,
    )
    view_data.qimage = convert_numpy_to_qimage(view_data.adjusted_array)


def create_window_level_preview(
    view_data,
    max_size=1024,
    brightness=0,
    contrast=1.0,
    negative=False,
):
    """Create a temporary reduced display image for responsive mouse dragging."""
    if view_data.original_array is None:
        return None
    preview_source = downsample_array(view_data.original_array, max_size=max_size)
    if preview_source is None:
        return None
    preview_base = apply_rescale_window(
        preview_source,
        view_data.rescale_slope,
        view_data.rescale_intercept,
        view_data.wc,
        view_data.ww,
        view_data.photometric_interpretation,
    )
    preview_adjusted = apply_brightness_contrast(
        preview_base,
        brightness,
        contrast,
        negative,
    )
    preview_image = convert_numpy_to_qimage(preview_adjusted)
    del preview_source, preview_base, preview_adjusted
    return preview_image


def load_thumbnail_qimage(file_path, max_size=160):
    """Decode one frame, immediately downsample it and release the full buffer."""
    extension = os.path.splitext(file_path)[1].lower()
    if extension in DICOM_EXTS:
        dataset = _read_dicom_metadata(file_path)
        if not _has_pixel_data(dataset):
            raise InvalidMetadataError(file_path, "Нет пиксельных данных для превью")
        full_array = _decode_dicom_frame(file_path, dataset, 0)
        preview_array = downsample_array(np.asarray(full_array), max_size=max_size)
        del full_array
        gc.collect()
        if preview_array is None:
            return None
        wc = _safe_float(_first_value(dataset.get("WindowCenter")), None, file_path, "WindowCenter")
        ww = _safe_float(_first_value(dataset.get("WindowWidth")), None, file_path, "WindowWidth")
        slope = _safe_float(dataset.get("RescaleSlope"), 1.0, file_path, "RescaleSlope")
        intercept = _safe_float(dataset.get("RescaleIntercept"), 0.0, file_path, "RescaleIntercept")
        photometric = str(dataset.get("PhotometricInterpretation", "MONOCHROME2"))
        display = apply_rescale_window(preview_array, slope, intercept, wc, ww, photometric)
        del dataset, preview_array
    elif extension in IMAGE_EXTS:
        if not PIL_AVAILABLE:
            return None
        from PIL import Image as PILImage

        with PILImage.open(file_path) as image:
            image.thumbnail((max_size, max_size))
            display = np.asarray(image.convert("RGB"))
    elif extension in JSON_EXTS:
        view_data = load_json_file(file_path)
        preview_array = downsample_array(view_data.original_array, max_size=max_size)
        display = normalize_image(preview_array)
        del view_data, preview_array
    else:
        return None

    qimage = convert_numpy_to_qimage(np.ascontiguousarray(display))
    del display
    gc.collect()
    return qimage
