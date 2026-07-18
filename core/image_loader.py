import os
import json
import traceback
import numpy as np
import pydicom
from pydicom.errors import InvalidDicomError
from core.utils import (
    fix_dicom_encoding, format_dicom_date, format_dicom_time,
    PIL_AVAILABLE, DICOM_EXTS, IMAGE_EXTS, JSON_EXTS, SUPPORTED_EXTS
)
from core.image_processor import apply_rescale, apply_window_level, normalize_image, apply_brightness_contrast
from core.utils import convert_numpy_to_qimage
from models.view_data import ViewData

try:
    import pydicom.pixel_data_handlers.gdcm_handler as _gdcm_handler
    import pydicom.pixel_data_handlers.pylibjpeg_handler as _pylibjpeg_handler
except ImportError:
    pass


def load_dicom_file(file_path):
    try:
        ds = pydicom.dcmread(file_path, force=True)
        if 'PixelData' not in ds:
            raise ValueError("Файл не содержит тег PixelData.")

        try:
            pixel_array = ds.pixel_array
        except Exception as e:
            ts = ds.file_meta.TransferSyntaxUID if hasattr(ds, 'file_meta') else 'Unknown UID'
            msg = (
                f"Не удалось распаковать пиксельные данные.\n"
                f"Синтаксис: {ts.name if hasattr(ts, 'name') else ts}\n"
                f"Возможно, нужно установить доп. библиотеки: pip install pydicom[gdcm] pylibjpeg\n\nОшибка: {e}"
            )
            raise RuntimeError(msg) from e

        if pixel_array is None or pixel_array.size == 0:
            raise ValueError("pixel_array пустой.")

        num_frames = getattr(ds, 'NumberOfFrames', 1)
        display_array = pixel_array[0] if num_frames > 1 and pixel_array.ndim > 2 else pixel_array

        vd = ViewData()
        vd.file_path = file_path
        vd.original_array = display_array.copy()
        vd.file_type = 'dicom'
        vd.photometric_interpretation = ds.get('PhotometricInterpretation', 'MONOCHROME2')
        vd.rescale_slope = float(ds.get('RescaleSlope', 1.0))
        vd.rescale_intercept = float(ds.get('RescaleIntercept', 0.0))
        vd.number_of_frames = num_frames

        def get_first_val(value):
            return value[0] if isinstance(value, pydicom.multival.MultiValue) and value else value

        wc_val = get_first_val(ds.get('WindowCenter'))
        ww_val = get_first_val(ds.get('WindowWidth'))
        if wc_val is None or ww_val is None:
            voi_lut_seq = ds.get('VOILUTSequence')
            if voi_lut_seq:
                wc_val = get_first_val(voi_lut_seq[0].get('WindowCenter', wc_val))
                ww_val = get_first_val(voi_lut_seq[0].get('WindowWidth', ww_val))

        vd.wc = float(wc_val) if wc_val is not None else None
        vd.ww = float(ww_val) if ww_val is not None and float(ww_val) >= 1 else None

        ps_val = get_first_val(ds.get('PixelSpacing', ds.get('ImagerPixelSpacing')))
        vd.pixel_spacing = float(ps_val[0] if isinstance(ps_val, list) else ps_val) if ps_val else 1.0
        if vd.pixel_spacing < 1e-9:
            vd.pixel_spacing = 1.0

        vd.patient_name = fix_dicom_encoding(str(ds.get('PatientName', 'N/A')))
        vd.patient_id = fix_dicom_encoding(str(ds.get('PatientID', 'N/A')))
        vd.patient_birth_date = format_dicom_date(ds.get('PatientBirthDate', ''))
        vd.patient_sex = str(ds.get('PatientSex', 'N/A'))
        vd.study_date = format_dicom_date(ds.get('StudyDate', ''))
        vd.study_time = format_dicom_time(ds.get('StudyTime', ''))
        vd.study_description = fix_dicom_encoding(str(ds.get('StudyDescription', 'N/A')))
        vd.modality = str(ds.get('Modality', 'N/A'))
        vd.institution_name = fix_dicom_encoding(str(ds.get('InstitutionName', 'N/A')))
        vd.body_part = fix_dicom_encoding(str(ds.get('BodyPartExamined', 'N/A')))
        vd.view_position = str(ds.get('ViewPosition', ''))
        vd.series_description = fix_dicom_encoding(str(ds.get('SeriesDescription', '')))

        return vd
    except Exception as e:
        msg = f"Ошибка обработки DICOM:\n{os.path.basename(file_path)}\n\n{type(e).__name__}: {e}"
        raise RuntimeError(msg) from e


def load_image_file(file_path):
    if not PIL_AVAILABLE:
        raise RuntimeError("Для загрузки изображений необходимо установить Pillow:\npip install Pillow")
    try:
        from PIL import Image as PILImage
        with PILImage.open(file_path) as img:
            if img.mode != 'L':
                img_array = np.array(img.convert('L'))
            else:
                img_array = np.array(img)

        vd = ViewData()
        vd.file_path = file_path
        vd.original_array = img_array.copy()
        vd.file_type = 'image'
        vd.number_of_frames = 1
        vd.photometric_interpretation = 'MONOCHROME2'
        vd.rescale_slope = 1.0
        vd.rescale_intercept = 0.0
        vd.wc = None
        vd.ww = None
        vd.pixel_spacing = 1.0
        vd.patient_name = os.path.basename(file_path)
        vd.patient_id = 'IMAGE'
        vd.study_description = f'Изображение {os.path.splitext(file_path)[1].upper()}'
        vd.modality = 'IMG'

        return vd
    except Exception as e:
        msg = f"Ошибка загрузки изображения:\n{os.path.basename(file_path)}\n\n{type(e).__name__}: {e}"
        raise RuntimeError(msg) from e


def load_json_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        image_data = None
        if isinstance(data, dict):
            possible_keys = ['image', 'data', 'array', 'pixels', 'pixel_data']
            for key in possible_keys:
                if key in data:
                    image_data = data[key]
                    break
            if image_data is None and all(isinstance(v, (list, int, float)) for v in data.values()):
                image_data = list(data.values())
        elif isinstance(data, list):
            image_data = data

        if image_data is not None:
            img_array = np.array(image_data)
            if img_array.ndim >= 2 and img_array.size > 0:
                if img_array.dtype != np.uint8:
                    img_min, img_max = np.min(img_array), np.max(img_array)
                    if img_max > img_min:
                        img_array = ((img_array - img_min) / (img_max - img_min) * 255).astype(np.uint8)
                    else:
                        img_array = np.full(img_array.shape, 128, dtype=np.uint8)
                if img_array.ndim > 2:
                    img_array = img_array[0]

                vd = ViewData()
                vd.file_path = file_path
                vd.original_array = img_array.copy()
                vd.file_type = 'json'
                vd.photometric_interpretation = 'MONOCHROME2'
                vd.patient_name = os.path.basename(file_path)
                vd.patient_id = 'JSON'
                vd.pixel_spacing = 1.0
                return vd
            else:
                raise ValueError("JSON не содержит подходящих данных для изображения")
        else:
            raise ValueError("Не найдены данные изображения в JSON")
    except Exception as e:
        msg = f"Ошибка загрузки JSON:\n{os.path.basename(file_path)}\n\n{type(e).__name__}: {e}"
        raise RuntimeError(msg) from e


def load_generic_file(file_path):
    if not file_path or not os.path.exists(file_path):
        return None
    ext = os.path.splitext(file_path)[1].lower()
    if ext in DICOM_EXTS:
        return load_dicom_file(file_path)
    elif ext in IMAGE_EXTS:
        return load_image_file(file_path)
    elif ext in JSON_EXTS:
        return load_json_file(file_path)
    return None


def apply_adjustments_pipeline(vd, brightness=0, contrast=1.0, negative=False):
    if vd.original_array is None:
        vd.rescaled_array = None
        vd.base_8bit_array = None
        vd.adjusted_array = None
        vd.qimage = None
        return

    try:
        vd.rescaled_array = apply_rescale(vd.original_array, vd.rescale_slope, vd.rescale_intercept)
        pi = vd.photometric_interpretation
        if vd.wc is not None and vd.ww is not None:
            vd.base_8bit_array = apply_window_level(vd.rescaled_array, vd.wc, vd.ww, pi)
        else:
            vd.base_8bit_array = normalize_image(vd.rescaled_array, pi)
        vd.adjusted_array = apply_brightness_contrast(vd.base_8bit_array, brightness, contrast, negative)
        vd.qimage = convert_numpy_to_qimage(vd.adjusted_array)
    except Exception as e:
        print(f"Error applying adjustments pipeline: {e}")
        vd.rescaled_array = None
        vd.base_8bit_array = None
        vd.adjusted_array = None
        vd.qimage = None


def update_brightness_contrast_only(vd, brightness=0, contrast=1.0, negative=False):
    if vd.base_8bit_array is None:
        return
    new_adj = apply_brightness_contrast(vd.base_8bit_array, brightness, contrast, negative)
    if new_adj is not None:
        vd.adjusted_array = new_adj
        vd.qimage = convert_numpy_to_qimage(vd.adjusted_array)
