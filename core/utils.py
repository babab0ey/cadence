import traceback
import numpy as np
from PyQt6 import QtGui


DICOM_EXTS = {'.dcm', '.dicom', '.ima', '.img'}
IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff'}
JSON_EXTS = {'.json'}
SUPPORTED_EXTS = DICOM_EXTS | IMAGE_EXTS | JSON_EXTS
PRIORITY_EXTS = DICOM_EXTS

DICOM_PRESETS = {
    "По умолчанию": None,
    "Лёгкие (Lungs)": (-600, 1500),
    "Кости (Bone)": (400, 1800),
    "Мозг (Brain)": (40, 80),
    "Мягкие ткани (Soft Tissue)": (40, 400),
    "Печень (Liver)": (60, 150),
    "Средостение": (50, 350)
}

PIL_AVAILABLE = False
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    print("Warning: Pillow не установлен. Поддержка PNG/JPEG недоступна.")


def _has_declared_character_set(specific_character_set):
    """Return whether DICOM metadata explicitly declares a text encoding."""
    if isinstance(specific_character_set, (list, tuple)):
        return any(str(value).strip() for value in specific_character_set)
    return bool(str(specific_character_set).strip()) if specific_character_set is not None else False


def fix_dicom_encoding(text, specific_character_set=None):
    """Repair only high-confidence CP1251-as-Latin-1 mojibake.

    Pydicom already honours SpecificCharacterSet.  Re-decoding text after that can
    corrupt valid names such as ``Müller`` or ``José``, so declared encodings and
    ambiguous strings are deliberately returned unchanged.
    """
    if not isinstance(text, str) or not text or _has_declared_character_set(specific_character_set):
        return text
    if any("\u0400" <= char <= "\u052f" for char in text):
        return text

    significant = [char for char in text if char.isalpha()]
    latin1_suspects = [char for char in significant if "\u0080" <= char <= "\u00ff"]
    if len(latin1_suspects) < 4 or len(latin1_suspects) / max(len(significant), 1) < 0.65:
        return text

    try:
        candidate = text.encode("latin1").decode("cp1251")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text

    candidate_letters = [char for char in candidate if char.isalpha()]
    cyrillic_letters = [char for char in candidate_letters if "\u0400" <= char <= "\u052f"]
    cyrillic_ratio = len(cyrillic_letters) / max(len(candidate_letters), 1)
    has_russian_vowel = any(char.lower() in "аеёиоуыэюя" for char in cyrillic_letters)
    if len(cyrillic_letters) >= 4 and cyrillic_ratio >= 0.7 and has_russian_vowel:
        return candidate
    return text


def convert_numpy_to_qimage(pixel_array):
    if pixel_array is None or pixel_array.size == 0:
        return QtGui.QImage()
    img_to_convert = pixel_array
    if img_to_convert.dtype != np.uint8:
        from core.image_processor import normalize_image
        img_to_convert = normalize_image(img_to_convert)
        if img_to_convert is None:
            return QtGui.QImage()
    if not img_to_convert.flags['C_CONTIGUOUS']:
        try:
            img_to_convert = np.ascontiguousarray(img_to_convert)
        except Exception as e:
            print(f"Error making array C-contiguous: {e}")
            return QtGui.QImage()
    try:
        height, width = img_to_convert.shape[:2]
        if img_to_convert.ndim == 2:
            bytes_per_line = width
            if img_to_convert.dtype != np.uint8:
                return QtGui.QImage()
            qimg = QtGui.QImage(img_to_convert.data, width, height, bytes_per_line,
                                QtGui.QImage.Format.Format_Grayscale8)
        elif img_to_convert.ndim == 3 and img_to_convert.shape[2] == 3:
            bytes_per_line = 3 * width
            if img_to_convert.dtype != np.uint8:
                return QtGui.QImage()
            qimg = QtGui.QImage(img_to_convert.data, width, height, bytes_per_line,
                                QtGui.QImage.Format.Format_RGB888)
        elif img_to_convert.ndim == 3 and img_to_convert.shape[2] == 4:
            bytes_per_line = 4 * width
            if img_to_convert.dtype != np.uint8:
                return QtGui.QImage()
            qimg = QtGui.QImage(img_to_convert.data, width, height, bytes_per_line,
                                QtGui.QImage.Format.Format_RGBA8888)
        else:
            print(f"Error: Unsupported dims {img_to_convert.shape}")
            return QtGui.QImage()
        return qimg.copy()
    except Exception as e:
        print(f"Error creating QImage: {e}")
        traceback.print_exc()
        return QtGui.QImage()


def format_dicom_date(date_str):
    if not date_str or not isinstance(date_str, str) or len(date_str) != 8:
        return 'N/A'
    try:
        return f"{date_str[6:8]}.{date_str[4:6]}.{date_str[0:4]}"
    except (IndexError, TypeError):
        return date_str


def format_dicom_time(time_str):
    if not time_str or not isinstance(time_str, str):
        return 'N/A'
    try:
        t = time_str.split('.')[0]
        if len(t) >= 6:
            return f"{t[0:2]}:{t[2:4]}:{t[4:6]}"
        elif len(t) >= 4:
            return f"{t[0:2]}:{t[2:4]}:00"
        return str(time_str)
    except (IndexError, TypeError, ValueError):
        return str(time_str)
