"""Theme-aware Lucide icons bundled with the application.

The SVG files in ``resources/lucide`` come from lucide-static 0.468.0
(ISC license).  Keeping the assets local makes the packaged viewer fully
offline and guarantees one consistent line-icon family throughout the UI.
"""

from functools import lru_cache
from pathlib import Path

from PyQt6 import QtCore, QtGui, QtSvg


ICON_DIR = Path(__file__).resolve().parent / "lucide"

# Compatibility aliases keep the existing business/UI wiring stable while all
# rendered artwork now comes from Lucide rather than hand-drawn mixed SVGs.
ICON_ALIASES = {
    "file-open": "file-plus-2",
    "trash": "trash-2",
    "cursor": "mouse-pointer-2",
    "pen": "pen-line",
    "rectangle": "scan",
    "ellipse": "scan",
    "polygon": "scan",
    "angle": "drafting-compass",
    "note": "notebook-pen",
    "zoom-reset": "maximize",
    "zoom-center": "scan",
    "rotate": "rotate-cw",
    "flip-h": "flip-horizontal-2",
    "flip-v": "flip-vertical-2",
    "undo": "undo-2",
    "redo": "redo-2",
    "adjust": "contrast",
    "help": "circle-help",
    "more": "ellipsis",
    "layout-single": "square",
    "layout-double": "columns-2",
    "layout-quad": "grid-2x2",
    "focus": "maximize-2",
    "preset": "sliders-horizontal",
    "anthropic-star": "sparkles",
}


@lru_cache(maxsize=256)
def _svg_source(name: str) -> str:
    actual_name = ICON_ALIASES.get(name, name)
    path = ICON_DIR / f"{actual_name}.svg"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


@lru_cache(maxsize=1024)
def _render_png_bytes(name: str, color: str, size: int, dpr: int = 2) -> bytes:
    source = _svg_source(name)
    if not source:
        return b""
    source = source.replace("currentColor", color)
    renderer = QtSvg.QSvgRenderer(QtCore.QByteArray(source.encode("utf-8")))
    if not renderer.isValid():
        return b""
    image = QtGui.QImage(size * dpr, size * dpr, QtGui.QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(image)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, True)
    renderer.render(painter)
    painter.end()
    image.setDevicePixelRatio(float(dpr))
    byte_array = QtCore.QByteArray()
    buffer = QtCore.QBuffer(byte_array)
    buffer.open(QtCore.QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(byte_array)


def make_pixmap(name: str, color: str = "#24221F", size: int = 20) -> QtGui.QPixmap:
    data = _render_png_bytes(name, color, int(size))
    pixmap = QtGui.QPixmap()
    if data:
        pixmap.loadFromData(data, "PNG")
    return pixmap


def make_icon(name: str, color: str = "#24221F", size: int = 20) -> QtGui.QIcon:
    pixmap = make_pixmap(name, color, size)
    return QtGui.QIcon(pixmap) if not pixmap.isNull() else QtGui.QIcon()
