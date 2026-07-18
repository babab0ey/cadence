"""
Claude-style SVG icons - vector icons matching anthropic design language.
All icons are rendered from inline SVG strings, colored to match the current theme.
"""
from PyQt6 import QtGui, QtCore, QtSvg
from PyQt6.QtCore import Qt, QByteArray


# Each icon: 20x20 viewBox, stroke-based, 1.5px stroke
ICONS = {
    "folder-open": '''
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none">
            <path d="M3 6.5C3 5.67157 3.67157 5 4.5 5H8L9.5 6.5H15.5C16.3284 6.5 17 7.17157 17 8V14.5C17 15.3284 16.3284 16 15.5 16H4.5C3.67157 16 3 15.3284 3 14.5V6.5Z"
                stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
        </svg>
    ''',
    "file-open": '''
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none">
            <path d="M11 3H5.5C4.67157 3 4 3.67157 4 4.5V15.5C4 16.3284 4.67157 17 5.5 17H14.5C15.3284 17 16 16.3284 16 15.5V8M11 3L16 8M11 3V7.5C11 7.77614 11.2239 8 11.5 8H16"
                stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/>
        </svg>
    ''',
    "save": '''
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none">
            <path d="M10 3.5V12.5M10 12.5L6 8.5M10 12.5L14 8.5M3.5 14V15.5C3.5 16.0523 3.94772 16.5 4.5 16.5H15.5C16.0523 16.5 16.5 16.0523 16.5 15.5V14"
                stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
    ''',
    "info": '''
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none">
            <circle cx="10" cy="10" r="7" stroke="currentColor" stroke-width="1.5"/>
            <path d="M10 9V13.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            <circle cx="10" cy="6.5" r="0.85" fill="currentColor"/>
        </svg>
    ''',
    "trash": '''
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none">
            <path d="M4 6H16M8 6V4.5C8 4.22386 8.22386 4 8.5 4H11.5C11.7761 4 12 4.22386 12 4.5V6M5.5 6L6.2 15.1C6.24 15.65 6.7 16 7.25 16H12.75C13.3 16 13.76 15.65 13.8 15.1L14.5 6"
                stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
    ''',
    "eraser": '''
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none">
            <path d="M12.5 4L4 12.5L7.5 16H10L16 10L12.5 4Z"
                stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
            <path d="M8 8.5L11.5 12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
    ''',
    "x": '''
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none">
            <path d="M5 5L15 15M15 5L5 15" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
    ''',
    "cursor": '''
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none">
            <path d="M4.5 3L14 9.5L9.5 11L8 16L4.5 3Z"
                stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" fill="none"/>
        </svg>
    ''',
    "ruler": '''
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none">
            <rect x="2" y="7" width="16" height="6" rx="1" transform="rotate(-22 10 10)"
                stroke="currentColor" stroke-width="1.5"/>
            <path d="M6 8L7 10M8.5 6.5L9.5 8.5M11 5L12 7M13.5 3.5L14.5 5.5"
                stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
        </svg>
    ''',
    "pen": '''
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none">
            <path d="M14 3.5L16.5 6L7 15.5L3.5 16.5L4.5 13L14 3.5Z"
                stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
            <path d="M12 5.5L14.5 8" stroke="currentColor" stroke-width="1.5"/>
        </svg>
    ''',
    "rectangle": '''
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none">
            <rect x="3.5" y="5" width="13" height="10" rx="1.5" stroke="currentColor"
                stroke-width="1.5" stroke-dasharray="2.5 2"/>
        </svg>
    ''',
    "ellipse": '''
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none">
            <ellipse cx="10" cy="10" rx="7" ry="5" stroke="currentColor"
                stroke-width="1.5" stroke-dasharray="2.5 2"/>
        </svg>
    ''',
    "polygon": '''
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none">
            <path d="M10 3L17 8L14 16H6L3 8L10 3Z" stroke="currentColor"
                stroke-width="1.5" stroke-linejoin="round" stroke-dasharray="2.5 2"/>
        </svg>
    ''',
    "angle": '''
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none">
            <path d="M3 17L17 17M3 17L3 3" stroke="currentColor"
                stroke-width="1.5" stroke-linecap="round"/>
            <path d="M3 9C4.5 9 8 11 8 17" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
        </svg>
    ''',
    "note": '''
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none">
            <path d="M4 4.5C4 4.22 4.22 4 4.5 4H13L16 7V15.5C16 15.78 15.78 16 15.5 16H4.5C4.22 16 4 15.78 4 15.5V4.5Z"
                stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
            <path d="M7 9.5L13 9.5M7 12L11 12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
    ''',
    "zoom-in": '''
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none">
            <circle cx="9" cy="9" r="5.5" stroke="currentColor" stroke-width="1.5"/>
            <path d="M9 7V11M7 9H11M13 13L17 17" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
    ''',
    "zoom-out": '''
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none">
            <circle cx="9" cy="9" r="5.5" stroke="currentColor" stroke-width="1.5"/>
            <path d="M7 9H11M13 13L17 17" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
    ''',
    "zoom-reset": '''
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none">
            <circle cx="9" cy="9" r="5.5" stroke="currentColor" stroke-width="1.5"/>
            <path d="M13 13L17 17" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            <path d="M9 6V12M6 9H12" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-dasharray="1.5 1.5"/>
        </svg>
    ''',
    "zoom-center": '''
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none">
            <rect x="3" y="3" width="14" height="14" rx="1.5" stroke="currentColor" stroke-width="1.5"/>
            <path d="M10 7V13M7 10H13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
    ''',
    "rotate": '''
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none">
            <path d="M16 6V10H12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M16 10C16 6.69 13.31 4 10 4C7.5 4 5.35 5.53 4.5 7.5"
                stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            <path d="M4 14V10H8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M4 10C4 13.31 6.69 16 10 16C12.5 16 14.65 14.47 15.5 12.5"
                stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
    ''',
    "flip-h": '''
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none">
            <path d="M10 3V17" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-dasharray="2 2"/>
            <path d="M3 6L8 6L8 14L3 14L3 6Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
            <path d="M17 6L12 6L12 14L17 14L17 6Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" stroke-dasharray="2 1.5"/>
        </svg>
    ''',
    "flip-v": '''
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none">
            <path d="M3 10H17" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-dasharray="2 2"/>
            <path d="M6 3L6 8L14 8L14 3L6 3Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
            <path d="M6 17L6 12L14 12L14 17L6 17Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" stroke-dasharray="2 1.5"/>
        </svg>
    ''',
    "undo": '''
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none">
            <path d="M7 6L3 10L7 14" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M3 10H12C14.7614 10 17 12.2386 17 15"
                stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
    ''',
    "redo": '''
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none">
            <path d="M13 6L17 10L13 14" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M17 10H8C5.2386 10 3 12.2386 3 15"
                stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
    ''',
    "adjust": '''
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none">
            <circle cx="10" cy="10" r="6.5" stroke="currentColor" stroke-width="1.5"/>
            <path d="M10 3.5V16.5" stroke="currentColor" stroke-width="1.5"/>
            <path d="M10 3.5C13.5899 3.5 16.5 6.41015 16.5 10C16.5 13.5899 13.5899 16.5 10 16.5"
                fill="currentColor"/>
        </svg>
    ''',
    "settings": '''
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none">
            <circle cx="10" cy="10" r="2.5" stroke="currentColor" stroke-width="1.5"/>
            <path d="M10 3V4.5M10 15.5V17M17 10H15.5M4.5 10H3M15 5L13.9 6.1M6.1 13.9L5 15M15 15L13.9 13.9M6.1 6.1L5 5"
                stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
    ''',
    "help": '''
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none">
            <circle cx="10" cy="10" r="7" stroke="currentColor" stroke-width="1.5"/>
            <path d="M8 8C8 6.89543 8.89543 6 10 6C11.1046 6 12 6.89543 12 8C12 8.7 11.5 9.3 10.8 9.7C10.3 10 10 10.5 10 11.1V11.5"
                stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            <circle cx="10" cy="14" r="0.85" fill="currentColor"/>
        </svg>
    ''',
    "more": '''
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
            <circle cx="4.5" cy="10" r="1.4"/>
            <circle cx="10" cy="10" r="1.4"/>
            <circle cx="15.5" cy="10" r="1.4"/>
        </svg>
    ''',
    "layout-single": '''
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none">
            <rect x="3.5" y="3.5" width="13" height="13" rx="2" stroke="currentColor" stroke-width="1.5"/>
        </svg>
    ''',
    "layout-double": '''
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none">
            <rect x="3.5" y="3.5" width="5.75" height="13" rx="1.5" stroke="currentColor" stroke-width="1.5"/>
            <rect x="10.75" y="3.5" width="5.75" height="13" rx="1.5" stroke="currentColor" stroke-width="1.5"/>
        </svg>
    ''',
    "layout-quad": '''
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none">
            <rect x="3.5" y="3.5" width="5.75" height="5.75" rx="1.2" stroke="currentColor" stroke-width="1.5"/>
            <rect x="10.75" y="3.5" width="5.75" height="5.75" rx="1.2" stroke="currentColor" stroke-width="1.5"/>
            <rect x="3.5" y="10.75" width="5.75" height="5.75" rx="1.2" stroke="currentColor" stroke-width="1.5"/>
            <rect x="10.75" y="10.75" width="5.75" height="5.75" rx="1.2" stroke="currentColor" stroke-width="1.5"/>
        </svg>
    ''',
    "search": '''
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none">
            <circle cx="9" cy="9" r="5.5" stroke="currentColor" stroke-width="1.5"/>
            <path d="M13 13L17 17" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
    ''',
    "sun": '''
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none">
            <circle cx="10" cy="10" r="3" stroke="currentColor" stroke-width="1.5"/>
            <path d="M10 2.5V4M10 16V17.5M17.5 10H16M4 10H2.5M15.3 4.7L14.2 5.8M5.8 14.2L4.7 15.3M15.3 15.3L14.2 14.2M5.8 5.8L4.7 4.7"
                stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
    ''',
    "moon": '''
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none">
            <path d="M16 12.5C15.1 13 14 13.3 12.9 13.3C9.4 13.3 6.6 10.5 6.6 7C6.6 5.9 6.9 4.9 7.4 4C5 4.9 3.3 7.3 3.3 10C3.3 13.5 6.2 16.4 9.7 16.4C12.4 16.4 14.8 14.7 16 12.5Z"
                stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
        </svg>
    ''',
    "focus": '''
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none">
            <path d="M3 7V4.5C3 3.67 3.67 3 4.5 3H7" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            <path d="M17 7V4.5C17 3.67 16.33 3 15.5 3H13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            <path d="M3 13V15.5C3 16.33 3.67 17 4.5 17H7" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            <path d="M17 13V15.5C17 16.33 16.33 17 15.5 17H13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
    ''',
    "image": '''
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none">
            <rect x="3" y="3.5" width="14" height="13" rx="1.5" stroke="currentColor" stroke-width="1.5"/>
            <circle cx="7" cy="7.5" r="1.2" stroke="currentColor" stroke-width="1.5"/>
            <path d="M3 13.5L7 10L10 12L14 8L17 11" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
        </svg>
    ''',
    "preset": '''
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none">
            <path d="M4 5H16M4 10H16M4 15H10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            <circle cx="14" cy="15" r="1.5" stroke="currentColor" stroke-width="1.5" fill="currentColor"/>
        </svg>
    ''',
    "chevron-down": '''
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none">
            <path d="M6 8L10 12L14 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
    ''',
    "chevron-left": '''
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none">
            <path d="M12 6L8 10L12 14" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
    ''',
    "chevron-right": '''
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none">
            <path d="M8 6L12 10L8 14" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
    ''',
    "anthropic-star": '''
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" fill="currentColor">
            <path d="m19.6 66.5 19.7-11 .3-1-.3-.5h-1l-3.3-.2-11.2-.3L14 53l-9.5-.5-2.4-.5L0 49l.2-1.5 2-1.3 2.9.2 6.3.5 9.5.6 6.9.4L38 49.1h1.6l.2-.7-.5-.4-.4-.4L29 41l-10.6-7-5.6-4.1-3-2-1.5-2-.6-4.2 2.7-3 3.7.3.9.2 3.7 2.9 8 6.1L37 36l1.5 1.2.6-.4.1-.3-.7-1.1L33 25l-6-10.4-2.7-4.3-.7-2.6c-.3-1-.4-2-.4-3l3-4.2L28 0l4.2.6L33.8 2l2.6 6 4.1 9.3L47 29.9l2 3.8 1 3.4.3 1h.7v-.5l.5-7.2 1-8.7 1-11.2.3-3.2 1.6-3.8 3-2L61 2.6l2 2.9-.3 1.8-1.1 7.7L59 27.1l-1.5 8.2h.9l1-1.1 4.1-5.4 6.9-8.6 3-3.5L77 13l2.3-1.8h4.3l3.1 4.7-1.4 4.9-4.4 5.6-3.7 4.7-5.3 7.1-3.2 5.7.3.4h.7l12-2.6 6.4-1.1 7.6-1.3 3.5 1.6.4 1.6-1.4 3.4-8.2 2-9.6 2-14.3 3.3-.2.1.2.3 6.4.6 2.8.2h6.8l12.6 1 3.3 2 1.9 2.7-.3 2-5.1 2.6-6.8-1.6-16-3.8-5.4-1.3h-.8v.4l4.6 4.5 8.3 7.5L89 80.1l.5 2.4-1.3 2-1.4-.2-9.2-7-3.6-3-8-6.8h-.5v.7l1.8 2.7 9.8 14.7.5 4.5-.7 1.4-2.6 1-2.7-.6-5.8-8-6-9-4.7-8.2-.5.4-2.9 30.2-1.3 1.5-3 1.2-2.5-2-1.4-3 1.4-6.2 1.6-8 1.3-6.4 1.2-7.9.7-2.6v-.2H49L43 72l-9 12.3-7.2 7.6-1.7.7-3-1.5.3-2.8L24 86l10-12.8 6-7.9 4-4.6-.1-.5h-.3L17.2 77.4l-4.7.6-2-2 .2-3 1-1 8-5.5Z"/>
        </svg>
    ''',
}


def _render_svg_to_pixmap(svg_text: str, color: str, size: int = 20) -> QtGui.QPixmap:
    """Render an SVG string into a QPixmap, replacing 'currentColor' with the given hex color."""
    colored = svg_text.replace("currentColor", color)
    renderer = QtSvg.QSvgRenderer(QByteArray(colored.encode("utf-8")))
    if not renderer.isValid():
        return QtGui.QPixmap()
    # render at 2x for retina, then downscale
    target_size = int(size * 2)
    pix = QtGui.QPixmap(target_size, target_size)
    pix.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(pix)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)
    renderer.render(painter)
    painter.end()
    pix.setDevicePixelRatio(2.0)
    return pix


def make_icon(name: str, color: str = "#3D3D3A", size: int = 20) -> QtGui.QIcon:
    """Return a QIcon for the named icon, rendered at the given color/size."""
    svg = ICONS.get(name)
    if not svg:
        return QtGui.QIcon()
    pix = _render_svg_to_pixmap(svg, color, size)
    if pix.isNull():
        return QtGui.QIcon()
    return QtGui.QIcon(pix)


def make_pixmap(name: str, color: str = "#3D3D3A", size: int = 20) -> QtGui.QPixmap:
    svg = ICONS.get(name)
    if not svg:
        return QtGui.QPixmap()
    return _render_svg_to_pixmap(svg, color, size)
