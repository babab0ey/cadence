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


def fix_dicom_encoding(text, target_encoding='cp1251', source_encoding_guess='latin1'):
    if not isinstance(text, str) or not text:
        return text
    needs_fix = any(0x80 <= ord(char) <= 0xFF for char in text)
    if needs_fix:
        try:
            original_bytes = text.encode(source_encoding_guess)
            correct_text = original_bytes.decode(target_encoding)
            return correct_text
        except (UnicodeEncodeError, UnicodeDecodeError, LookupError):
            return text
    else:
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
