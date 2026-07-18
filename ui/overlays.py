import re
import os
from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtCore import Qt
from core.workspace_manager import get_projection_info


PROJECTION_PRIORITY = [
    "RCC", "LCC", "RMLO", "LMLO", "RXCCL", "LXCCL", "RXCCM", "LXCCM",
    "RML", "LML", "RM", "LM", "MAG", "CV", "AX", "TAN", "RL", "FB", "TL",
    "PA", "AP", "LAT", "LL", "LATERAL", "CHEST", "CXR", "LUNGS",
    "RAP", "LAP", "RLAT", "LLAT", "R", "L",
    "CERVICAL", "THORACIC", "LUMBAR", "SPINE",
    "C1", "C2", "C3", "C4", "C5", "C6", "C7",
    "T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9", "T10", "T11", "T12",
    "L1", "L2", "L3", "L4", "L5",
    "PELVIS", "HIP", "RHIP", "LHIP",
    "SKULL", "HEAD", "CRANIUM",
    "FRONT", "BACK", "SIDE", "OBLIQUE"
]


def clear_overlay_items(scene, vd):
    if not scene:
        return
    for item in vd.overlay_items:
        if item and item.scene() == scene:
            try:
                scene.removeItem(item)
            except Exception:
                pass
    vd.overlay_items = []


def update_image_overlay(view_index, vd, scene, view, is_dark_theme=False, brightness=0, contrast=1.0, negative_mode=False):
    clear_overlay_items(scene, vd)
    pixmap_item = vd.pixmap_item
    if not pixmap_item or not scene or pixmap_item.pixmap().isNull():
        return

    overlay_font = QtGui.QFont("Segoe UI", 10, QtGui.QFont.Weight.DemiBold)
    overlay_color = QtGui.QColor("#D97757")  # Claude clay accent
    if is_dark_theme:
        overlay_color = QtGui.QColor("#F0B89C")  # softer in dark mode
    bounds = pixmap_item.boundingRect()
    scale = max(0.01, abs(view.transform().m11()))
    # Text is parented to the pixmap and therefore scales with the scene. Keep
    # its on-screen size near 12 px instead of enlarging it with the image. A
    # tiny matrix (for example a 10×10 dose sample) cannot carry readable
    # metadata without covering the pixels, so its overlay is intentionally
    # omitted.
    ideal_font_size = 12 / scale
    if ideal_font_size < 1.0:
        return
    font_size = max(1, min(96, round(ideal_font_size)))
    margin = max(2, round(8 / scale))

    overlay_font.setPixelSize(font_size)

    wc_str = f"{vd.wc:.0f}" if isinstance(vd.wc, (int, float)) else '—'
    ww_str = f"{vd.ww:.0f}" if isinstance(vd.ww, (int, float)) else '—'

    projection = _detect_projection(vd)

    def shortened(value, limit=24):
        text = str(value or "—")
        return text if len(text) <= limit else f"{text[:limit - 1]}…"

    info = {
        'tl': [shortened(vd.patient_name), f"Идентификатор: {shortened(vd.patient_id, 18)}"],
        'tr': [shortened(vd.institution_name, 20), f"Дата: {vd.study_date}"],
        'tc': [projection] if projection else [],
        'bl': [f"Яркость: {wc_str}", f"Контраст: {ww_str}", f"Масштаб: {scale:.1f}×"],
        'br': [f"{vd.modality} {get_projection_info(vd)}".strip(),
               "Негатив" if negative_mode else "Обычный вид"]
    }

    positions = {
        'tl': (bounds.left() + margin, bounds.top() + margin,
               Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop),
        'tr': (bounds.right() - margin, bounds.top() + margin,
               Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop),
        'tc': (bounds.center().x(), bounds.top() + margin,
               Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop),
        'bl': (bounds.left() + margin, bounds.bottom() - margin,
               Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom),
        'br': (bounds.right() - margin, bounds.bottom() - margin,
               Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
    }

    for key, lines in info.items():
        text_content = "\n".join(filter(None, lines))
        if not text_content:
            continue
        item = QtWidgets.QGraphicsSimpleTextItem(text_content)
        item.setFont(overlay_font)
        item.setBrush(overlay_color)
        item.setZValue(10)
        item._is_dicom_overlay = True
        scene.addItem(item)
        item.setParentItem(pixmap_item)
        x, y, alignment = positions[key]
        item_bounds = item.boundingRect()
        if alignment & Qt.AlignmentFlag.AlignRight:
            x -= item_bounds.width()
        elif alignment & Qt.AlignmentFlag.AlignHCenter:
            x -= item_bounds.width() / 2
        if alignment & Qt.AlignmentFlag.AlignBottom:
            y -= item_bounds.height()
        item.setPos(x, y)
        vd.overlay_items.append(item)


def _detect_projection(vd):
    projection = get_projection_info(vd)
    if projection and projection.upper() in [p.upper() for p in PROJECTION_PRIORITY]:
        return projection.upper()
    if vd.file_path:
        filename = os.path.basename(vd.file_path).upper()
        for modality in PROJECTION_PRIORITY:
            if re.search(rf"\b{modality}\b", filename):
                return modality
            elif modality in filename:
                return modality
    return projection
