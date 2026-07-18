import os
import re
from collections import defaultdict
from core.utils import DICOM_EXTS, IMAGE_EXTS, JSON_EXTS, SUPPORTED_EXTS
from models.view_data import ViewData


MAX_VIEWS = 4


def create_empty_view_data():
    return ViewData()


def get_mammo_sort_key(file_path):
    filename = os.path.basename(file_path).upper()
    pattern_priority = [
        "RCC", "LCC", "RMLO", "LMLO",
        "RXCCL", "LXCCL", "RXCCM", "LXCCM",
        "RML", "LML", "RM", "LM",
        "MAG", "CV", "AX", "TAN", "RL", "FB", "TL",
        "PA", "AP", "LAT", "LL", "LATERAL",
        "CHEST", "CXR", "LUNGS",
        "RAP", "LAP", "RLAT", "LLAT",
        "R", "L",
        "CERVICAL", "THORACIC", "LUMBAR", "SPINE",
        "C1", "C2", "C3", "C4", "C5", "C6", "C7",
        "T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9", "T10", "T11", "T12",
        "L1", "L2", "L3", "L4", "L5",
        "PELVIS", "HIP", "RHIP", "LHIP",
        "SKULL", "HEAD", "CRANIUM",
        "FRONT", "BACK", "SIDE", "OBLIQUE"
    ]
    for i, pattern in enumerate(pattern_priority, 1):
        if re.search(rf"\b{pattern}\b", filename):
            return (i, filename)
        if pattern in filename:
            return (i, filename)
    return (len(pattern_priority) + 1, filename)


def sort_files_for_mammo(file_paths):
    is_mammo_study = any(
        re.search(r'(CC|MLO|XCCL)', os.path.basename(f).upper(), re.IGNORECASE)
        for f in file_paths
    )
    is_xray_study = any(
        re.search(r'(PA|AP|LAT|CHEST|CXR)', os.path.basename(f).upper(), re.IGNORECASE)
        for f in file_paths
    )
    if is_mammo_study:
        print("Обнаружены маммографические проекции. Применяется автоматическая сортировка.")
    elif is_xray_study:
        print("Обнаружены рентгеновские проекции. Применяется автоматическая сортировка.")
    else:
        print("Специальные проекции не найдены. Стандартная сортировка по имени.")
    return sorted(file_paths, key=get_mammo_sort_key)


def scan_folder_for_files(folder_path):
    files_by_ext = defaultdict(list)
    try:
        for root, _, files in os.walk(folder_path):
            for filename in files:
                ext = os.path.splitext(filename)[1].lower()
                if ext in SUPPORTED_EXTS:
                    full_path = os.path.join(root, filename)
                    files_by_ext[ext].append(full_path)
    except Exception as e:
        print(f"Ошибка сканирования папки {folder_path}: {e}")
    return files_by_ext


def distribute_files(sorted_files):
    dicom_files = [f for f in sorted_files if os.path.splitext(f)[1].lower() in DICOM_EXTS]
    other_files = [f for f in sorted_files if os.path.splitext(f)[1].lower() not in DICOM_EXTS]
    files_for_main = dicom_files[:MAX_VIEWS]
    files_for_sidebar = dicom_files[MAX_VIEWS:] + other_files
    return files_for_main, files_for_sidebar


def determine_mode(num_files):
    if num_files >= 3:
        return 2
    elif num_files == 2:
        return 1
    return 0


def get_projection_info(vd):
    view_pos = vd.view_position.strip().upper()
    if view_pos:
        return view_pos
    series_desc = vd.series_description.strip().upper()
    if series_desc:
        mammo_keys = ['CC', 'MLO', 'XCCL', 'LM', 'ML', 'SIO']
        for key in mammo_keys:
            if key in series_desc:
                return series_desc
    if vd.file_path:
        filename = os.path.basename(vd.file_path).upper()
        match = re.search(r'\b(L|R)?(CC|MLO|XCCL)\b', filename)
        if match:
            return match.group(0)
    return ""
