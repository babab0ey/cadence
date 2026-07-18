"""Generate real UI captures using deterministic, entirely synthetic DICOM data."""

from __future__ import annotations

import math
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import pydicom
from PIL import Image, ImageDraw, ImageFilter
from PyQt6 import QtCore, QtGui, QtTest, QtWidgets
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage, generate_uid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from resources.design_tokens import GEOMETRY, build_stylesheet, register_inter_font
from ui.dialogs.info_dialog import DicomInfoDialog
from ui.main_window import DICOMViewer


OUTPUT = ROOT / "assets" / "screenshots"


def synthetic_mammogram(side: str, projection: str, seed: int, height: int = 920, width: int = 660) -> np.ndarray:
    """Create a mammography-like texture without using any human data."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:height, 0:width]
    y = yy / max(1, height - 1)
    x = xx / max(1, width - 1)

    vertical = (y - 0.51) / (0.48 if projection == "CC" else 0.52)
    reach = 0.90 * np.sqrt(np.clip(1.0 - vertical * vertical, 0.0, 1.0))
    if projection == "MLO":
        reach *= 0.98 - 0.18 * y
    tissue_coordinate = x if side == "R" else 1.0 - x
    mask = tissue_coordinate <= reach
    distance_to_skin = np.clip(reach - tissue_coordinate, 0.0, 1.0)

    base = 120 + 1250 * np.power(distance_to_skin, 0.56)
    base += 260 * (1.0 - np.abs(y - 0.52))
    noise = rng.normal(0.0, 72.0, size=(height, width))

    fiber_layer = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(fiber_layer)
    anchor_x = 18 if side == "R" else width - 18
    for _ in range(42):
        end_y = int(rng.uniform(height * 0.12, height * 0.90))
        end_x = int(rng.uniform(width * 0.20, width * 0.83))
        if side == "L":
            end_x = width - end_x
        middle_x = int((anchor_x + end_x) / 2 + rng.normal(0, width * 0.08))
        middle_y = int((height * 0.50 + end_y) / 2 + rng.normal(0, height * 0.08))
        draw.line(
            [(anchor_x, int(height * 0.50)), (middle_x, middle_y), (end_x, end_y)],
            fill=int(rng.integers(32, 115)),
            width=int(rng.integers(2, 8)),
            joint="curve",
        )
    fibers = np.asarray(fiber_layer.filter(ImageFilter.GaussianBlur(radius=5)), dtype=np.float32)

    texture = base + noise + fibers * 4.4
    for _ in range(10):
        cx = rng.uniform(0.18, 0.68) if side == "R" else rng.uniform(0.32, 0.82)
        cy = rng.uniform(0.22, 0.80)
        sx = rng.uniform(0.035, 0.11)
        sy = rng.uniform(0.035, 0.10)
        amplitude = rng.uniform(130, 460)
        texture += amplitude * np.exp(-(((x - cx) / sx) ** 2 + ((y - cy) / sy) ** 2) / 2.0)

    if projection == "MLO":
        chest_x = x if side == "R" else 1.0 - x
        pectoral = (chest_x < 0.24 * (1.0 - y)) & (y < 0.58)
        texture += pectoral * (920 * (1.0 - y))

    skin = mask & (distance_to_skin < 0.012)
    texture += skin * 520
    texture = np.where(mask, texture, rng.normal(18, 5, size=(height, width)))
    return np.clip(texture, 0, 4095).astype(np.uint16)


def write_synthetic_dicom(path: Path, array: np.ndarray, side: str, projection: str, instance: int) -> None:
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.ImplementationClassUID = generate_uid()

    dataset = FileDataset(str(path), {}, file_meta=meta, preamble=b"\0" * 128)
    dataset.SOPClassUID = meta.MediaStorageSOPClassUID
    dataset.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
    dataset.StudyInstanceUID = generate_uid()
    dataset.SeriesInstanceUID = generate_uid()
    dataset.PatientName = "SYNTHETIC^DEMO"
    dataset.PatientID = "DEMO-0001"
    dataset.PatientSex = "O"
    dataset.StudyDate = "20260115"
    dataset.StudyTime = "103000"
    dataset.StudyDescription = "SYNTHETIC MAMMOGRAPHY DEMO"
    dataset.SeriesDescription = f"SYNTHETIC {side}{projection}"
    dataset.InstitutionName = "DEMO MEDICAL CENTER"
    dataset.Manufacturer = "SYNTHETIC DATA GENERATOR"
    dataset.ManufacturerModelName = "NO MEDICAL DEVICE"
    dataset.Modality = "MG"
    dataset.BodyPartExamined = "BREAST"
    dataset.ViewPosition = projection
    dataset.Laterality = side
    dataset.InstanceNumber = instance
    dataset.Rows, dataset.Columns = array.shape
    dataset.SamplesPerPixel = 1
    dataset.PhotometricInterpretation = "MONOCHROME2"
    dataset.PixelSpacing = [0.10, 0.10]
    dataset.BitsAllocated = 16
    dataset.BitsStored = 12
    dataset.HighBit = 11
    dataset.PixelRepresentation = 0
    dataset.WindowCenter = 1450
    dataset.WindowWidth = 2700
    dataset.PixelData = np.ascontiguousarray(array).tobytes()
    pydicom.dcmwrite(str(path), dataset, enforce_file_format=True)


def wait_for(app: QtWidgets.QApplication, predicate, timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            raise TimeoutError("Timed out while preparing demo media")
        app.processEvents()
        QtTest.QTest.qWait(25)


def settle(app: QtWidgets.QApplication, milliseconds: int = 300) -> None:
    QtTest.QTest.qWait(milliseconds)
    app.processEvents()


def save_widget(widget: QtWidgets.QWidget, path: Path) -> None:
    settle(QtWidgets.QApplication.instance(), 220)
    pixmap = widget.grab()
    if pixmap.isNull() or not pixmap.save(str(path), "PNG"):
        raise RuntimeError(f"Unable to save screenshot: {path}")


def add_ruler(view, start: QtCore.QPointF, end: QtCore.QPointF) -> None:
    scale = max(0.1, abs(view.transform().m11()))
    view._ruler_tool.on_press(start, view.scene(), scale)
    view._ruler_tool.on_move(end, view.scene(), scale)
    view._ruler_tool.on_release(end, view.scene(), scale)
    view._register_current_annotations()


def add_angle(view, first: QtCore.QPointF, vertex: QtCore.QPointF, third: QtCore.QPointF) -> None:
    scale = max(0.1, abs(view.transform().m11()))
    view._angle_tool.on_press(first, view.scene(), scale)
    view._angle_tool.on_press(vertex, view.scene(), scale)
    view._angle_tool.on_press(third, view.scene(), scale)
    view._register_current_annotations()


def add_pen(view, points: list[QtCore.QPointF]) -> None:
    scale = max(0.1, abs(view.transform().m11()))
    view._pen_tool.on_press(points[0], view.scene(), scale)
    for point in points[1:-1]:
        view._pen_tool.on_move(point, view.scene(), scale)
    view._pen_tool.on_release(points[-1], view.scene(), scale)
    view._register_current_annotations()


def pixmap_to_pillow(pixmap: QtGui.QPixmap, width: int = 1000) -> Image.Image:
    temporary = OUTPUT / ".gif-frame.png"
    pixmap.save(str(temporary), "PNG")
    with Image.open(temporary) as source:
        frame = source.convert("RGB")
        if frame.width != width:
            height = round(frame.height * width / frame.width)
            frame = frame.resize((width, height), Image.Resampling.LANCZOS)
    temporary.unlink(missing_ok=True)
    return frame


def generate() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    app.setApplicationName("Просмотр снимков — синтетическое демо")
    app.setStyle("Fusion")
    family = register_inter_font()
    font = QtGui.QFont(family)
    font.setPixelSize(GEOMETRY["font_base"])
    app.setFont(font)
    app.setStyleSheet(build_stylesheet(False))

    with tempfile.TemporaryDirectory(prefix="synthetic-dicom-demo-") as temp_dir:
        demo_root = Path(temp_dir)
        definitions = (("R", "CC", 41), ("L", "CC", 42), ("R", "MLO", 43), ("L", "MLO", 44))
        paths: list[str] = []
        for instance, (side, projection, seed) in enumerate(definitions, 1):
            path = demo_root / f"{side}{projection}.dcm"
            write_synthetic_dicom(path, synthetic_mammogram(side, projection, seed), side, projection, instance)
            paths.append(str(path))

        window = DICOMViewer(settings=False)
        window.resize(1600, 920)
        window.show()
        window.is_dark_theme = True
        window.app_config["dark_theme"] = True
        window.app_config["theme_mode"] = "dark"
        window._apply_theme()
        window.load_files(paths)
        wait_for(app, lambda: window._batch_load_state is None and not window._pending_loads)
        for row in range(window.sidebar.model.rowCount()):
            window.sidebar.model.ensure_preview(row)
        window.sidebar.model.thumbnail_pool.waitForDone(-1)
        settle(app, 500)
        window.toolbar._update_responsive_state()
        save_widget(window, OUTPUT / "main-window-dark.png")

        window._setup_layout_for_mode(1)
        window.toolbar.set_current_mode(1)
        settle(app, 350)
        view0, view1 = window.all_views[:2]
        add_ruler(view0, QtCore.QPointF(105, 265), QtCore.QPointF(430, 570))
        add_angle(
            view1,
            QtCore.QPointF(115, 545),
            QtCore.QPointF(315, 345),
            QtCore.QPointF(505, 575),
        )
        add_pen(
            view0,
            [QtCore.QPointF(245 + i * 18, 450 + math.sin(i * 0.72) * 32) for i in range(10)],
        )
        save_widget(window, OUTPUT / "tools-and-measurements.png")

        data = window.view_data[0]
        dialog = DicomInfoDialog(
            0,
            data,
            window.all_views[0].transform().m11(),
            window.brightness,
            window.contrast,
            window.negative_mode,
            window.is_dark_theme,
            window,
        )
        dialog.resize(900, 760)
        dialog.show()
        settle(app, 400)
        save_widget(dialog, OUTPUT / "patient-info.png")
        dialog.close()

        window._setup_layout_for_mode(0)
        window.toolbar.set_current_mode(0)
        window.set_active_view(window.all_views[0])
        window.all_views[0].clear_all_drawing_items()
        settle(app, 300)
        frames: list[Image.Image] = []
        frames.extend([pixmap_to_pillow(window.grab())] * 2)
        add_ruler(window.all_views[0], QtCore.QPointF(120, 285), QtCore.QPointF(440, 575))
        settle(app, 220)
        frames.extend([pixmap_to_pillow(window.grab())] * 2)
        add_angle(
            window.all_views[0],
            QtCore.QPointF(155, 610),
            QtCore.QPointF(335, 410),
            QtCore.QPointF(515, 620),
        )
        settle(app, 220)
        frames.extend([pixmap_to_pillow(window.grab())] * 2)
        for brightness, contrast in ((-12, 82), (-6, 92), (0, 100), (7, 116), (13, 132), (7, 116), (0, 100)):
            window._on_values_applied(brightness, contrast, False)
            settle(app, 160)
            frames.append(pixmap_to_pillow(window.grab()))

        frames[0].save(
            OUTPUT / "tools-demo.gif",
            save_all=True,
            append_images=frames[1:],
            duration=[420, 420, 360, 360, 360, 360] + [190] * 7,
            loop=0,
            optimize=True,
            disposal=2,
        )
        window.close()
        app.processEvents()

    print(f"Generated synthetic demo media in: {OUTPUT}")
    print("No DICOM files were written outside the temporary directory.")


if __name__ == "__main__":
    generate()
