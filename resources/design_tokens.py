"""Single source of truth for the Claude-inspired application design system."""

from pathlib import Path
import re

from PyQt6 import QtGui, QtWidgets


LIGHT = {
    "bg_app": "#FAF9F6",
    "bg_panel": "#FFFFFF",
    "bg_input": "#F4F2EE",
    "bg_hover": "#F0EDE8",
    "bg_active": "#EBE7E0",
    "text_primary": "#24221F",
    "text_secondary": "#6B6660",
    "text_disabled": "#A8A39D",
    "text_on_accent": "#FFFFFF",
    "accent": "#D97757",
    "accent_hover": "#C96A47",
    "accent_light": "rgba(217, 119, 87, 28)",
    "border": "#E8E4DE",
    "border_focus": "#D97757",
    "shadow_color": "rgba(36, 34, 31, 20)",
    "viewer_bg": "#1A1918",
    "viewer_overlay": "#2A2826",
    "skeleton": "#302E2C",
    "skeleton_highlight": "#45413E",
}

DARK = {
    "bg_app": "#1F1E1C",
    "bg_panel": "#292826",
    "bg_input": "#333230",
    "bg_hover": "#3A3836",
    "bg_active": "#403E3C",
    "text_primary": "#F5F3EF",
    "text_secondary": "#9B9590",
    "text_disabled": "#6B6660",
    "text_on_accent": "#FFFFFF",
    "accent": "#D97757",
    "accent_hover": "#E8865F",
    "accent_light": "rgba(217, 119, 87, 38)",
    "border": "#3A3836",
    "border_focus": "#D97757",
    "shadow_color": "rgba(0, 0, 0, 64)",
    "viewer_bg": "#141312",
    "viewer_overlay": "#1F1E1C",
    "skeleton": "#272523",
    "skeleton_highlight": "#3B3835",
}

GEOMETRY = {
    "grid": 8,
    "radius_sm": 8,
    "radius_md": 12,
    "radius_lg": 16,
    "radius_xl": 20,
    "font_xs": 12,
    "font_sm": 13,
    "font_base": 15,
    "font_md": 16,
    "font_lg": 18,
    "font_xl": 22,
    "hit_target": 44,
    "toolbar_height": 56,
    "sidebar_collapsed": 48,
    "sidebar_min": 180,
    "sidebar_max": 360,
    "transition_fast": 150,
    "transition_base": 200,
    "transition_slow": 300,
}

STATUS = {
    "success": "#4CAF82",
    "warning": "#E8A838",
    "error": "#E05C5C",
    "info": "#5F86C9",
}


def theme_tokens(dark: bool = False) -> dict:
    return DARK if dark else LIGHT


def register_inter_font() -> str:
    """Register bundled Inter and return the best available UI family."""
    font_path = Path(__file__).resolve().parent / "fonts" / "InterVariable.ttf"
    if font_path.exists():
        font_id = QtGui.QFontDatabase.addApplicationFont(str(font_path))
        if font_id >= 0:
            families = QtGui.QFontDatabase.applicationFontFamilies(font_id)
            if families:
                return families[0]
    available = set(QtGui.QFontDatabase.families())
    for family in ("Segoe UI Variable", "Segoe UI"):
        if family in available:
            return family
    return QtWidgets.QApplication.font().family()


def apply_soft_shadow(widget, dark: bool = False, blur: int = 32, y_offset: int = 10):
    """Apply a warm low-opacity shadow to a floating surface."""
    tokens = theme_tokens(dark)
    effect = QtWidgets.QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, y_offset)
    effect.setColor(qcolor(tokens["shadow_color"]))
    widget.setGraphicsEffect(effect)
    return effect


def qcolor(value: str) -> QtGui.QColor:
    """Convert a design-token CSS color, including rgba(), to QColor."""
    match = re.fullmatch(r"rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([\d.]+)\s*\)", value)
    if not match:
        return QtGui.QColor(value)
    red, green, blue = (int(match.group(index)) for index in range(1, 4))
    alpha_value = float(match.group(4))
    alpha = round(alpha_value * 255) if alpha_value <= 1 else round(alpha_value)
    return QtGui.QColor(red, green, blue, max(0, min(255, alpha)))


def build_stylesheet(dark: bool = False) -> str:
    """Generate the complete Qt stylesheet from semantic tokens."""
    t = theme_tokens(dark)
    g = GEOMETRY
    return f"""
    * {{
        font-family: 'Inter', 'Segoe UI Variable', 'Segoe UI';
        font-size: {g['font_base']}px;
        color: {t['text_primary']};
        outline: none;
    }}
    QMainWindow, QWidget#centralRoot {{ background: {t['bg_app']}; }}
    QWidget {{ selection-background-color: {t['accent_light']}; selection-color: {t['text_primary']}; }}
    QLabel#mutedLabel, QLabel[role='secondary'] {{ color: {t['text_secondary']}; }}
    QLabel[role='caption'] {{ color: {t['text_secondary']}; font-size: {g['font_xs']}px; }}
    QLabel[role='sectionTitle'] {{ font-size: {g['font_lg']}px; font-weight: 600; }}
    QLabel#dialogTitle {{ font-size: {g['font_xl']}px; font-weight: 700; }}

    QPushButton, QToolButton {{
        min-height: 40px; border: 1px solid {t['border']}; border-radius: {g['radius_md']}px;
        background: transparent; padding: 0 16px; color: {t['text_primary']}; font-size: {g['font_base']}px;
    }}
    QPushButton:hover, QToolButton:hover {{ background: {t['bg_hover']}; }}
    QPushButton:pressed, QToolButton:pressed {{ background: {t['bg_active']}; }}
    QPushButton:focus, QToolButton:focus {{ border-color: {t['border_focus']}; }}
    QPushButton:disabled, QToolButton:disabled {{ color: {t['text_disabled']}; background: transparent; border-color: {t['border']}; }}
    QPushButton[buttonStyle='primary'] {{ background: {t['accent']}; border-color: {t['accent']}; color: {t['text_on_accent']}; font-weight: 600; }}
    QPushButton[buttonStyle='primary']:hover {{ background: {t['accent_hover']}; border-color: {t['accent_hover']}; }}
    QPushButton[buttonStyle='secondary'] {{ background: transparent; border-color: {t['border']}; color: {t['text_primary']}; font-weight: 550; }}
    QPushButton[segmentSelected='true'] {{ background: {t['accent_light']}; border-color: {t['accent']}; color: {t['accent']}; font-weight: 600; }}
    QPushButton[buttonStyle='ghost'], QToolButton[buttonStyle='ghost'] {{ background: transparent; border-color: transparent; color: {t['text_secondary']}; }}
    QPushButton[buttonStyle='ghost']:hover, QToolButton[buttonStyle='ghost']:hover {{ background: {t['bg_hover']}; color: {t['text_primary']}; }}
    QPushButton[iconOnly='true'], QToolButton[iconOnly='true'] {{ min-width: {g['hit_target']}px; max-width: {g['hit_target']}px; padding: 0; }}

    QToolBar#mainToolbar {{
        background: {t['bg_panel']}; border: none; border-bottom: 1px solid {t['border']};
        min-height: {g['toolbar_height']}px; max-height: {g['toolbar_height']}px; spacing: 4px;
    }}
    QWidget#toolbarSurface {{ background: {t['bg_panel']}; }}
    QFrame#toolbarSeparator {{ background: {t['border']}; min-width: 1px; max-width: 1px; min-height: 24px; max-height: 24px; }}

    QWidget#sidebarRoot {{ background: {t['bg_panel']}; border-right: 1px solid {t['border']}; }}
    QWidget#sidebarHeader {{ background: transparent; }}
    QLineEdit, QComboBox, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {{
        min-height: 40px; background: {t['bg_input']}; border: 1px solid transparent;
        border-radius: {g['radius_md']}px; padding: 0 14px; color: {t['text_primary']};
    }}
    QLineEdit:hover, QComboBox:hover {{ border-color: {t['border']}; }}
    QLineEdit:focus, QComboBox:focus, QTextEdit:focus {{ border-color: {t['border_focus']}; background: {t['bg_panel']}; }}
    QLineEdit::placeholder {{ color: {t['text_disabled']}; }}
    QListView#studyList {{ background: transparent; border: none; padding: 4px 8px 12px 8px; }}
    QListView#studyList::item {{ border: none; background: transparent; }}
    QScrollBar:vertical {{ background: transparent; width: 8px; margin: 4px 1px; }}
    QScrollBar::handle:vertical {{ background: {t['text_disabled']}; border-radius: 4px; min-height: 32px; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

    QGraphicsView {{ background: {t['viewer_bg']}; border: 1px solid {t['border']}; border-radius: {g['radius_lg']}px; }}
    QWidget#viewportStateOverlay {{ background: {t['viewer_bg']}; }}
    QWidget#viewportStateOverlay QLabel {{ color: #F5F3EF; background: transparent; }}
    QWidget#viewportStateOverlay QLabel[role='secondary'] {{ color: #9B9590; }}
    QWidget#viewportStateOverlay QPushButton[buttonStyle='ghost'] {{ color: #D8D4CF; }}
    QWidget#viewportStateOverlay QPushButton[buttonStyle='secondary'] {{ color: #F5F3EF; border-color: rgba(255,255,255,90); }}
    QWidget#viewportStateOverlay QPushButton[buttonStyle='secondary']:hover {{ color: #FFFFFF; background: rgba(255,255,255,18); border-color: rgba(255,255,255,135); }}
    QFrame#frameControls, QFrame#focusControls {{ background: {t['viewer_overlay']}; border: 1px solid rgba(255,255,255,24); border-radius: {g['radius_lg']}px; }}
    QFrame#focusControls QLabel, QFrame#focusControls QPushButton, QFrame#frameControls QLabel, QFrame#frameControls QPushButton {{ color: #F5F3EF; }}
    QLabel#focusHint {{ background: {t['viewer_overlay']}; color: #F5F3EF; border-radius: {g['radius_sm']}px; padding: 8px 12px; }}

    QDialog, QFrame#dialogSurface {{ background: {t['bg_panel']}; border: 1px solid {t['border']}; border-radius: {g['radius_xl']}px; }}
    QFrame#sectionCard {{ background: {t['bg_input']}; border: 1px solid {t['border']}; border-radius: {g['radius_md']}px; }}
    QFrame#infoBar {{ background: {t['bg_panel']}; border: 1px solid {t['border']}; border-radius: {g['radius_md']}px; }}

    QSlider::groove:horizontal {{ height: 4px; background: {t['border']}; border-radius: 2px; }}
    QSlider::sub-page:horizontal {{ background: {t['accent']}; border-radius: 2px; }}
    QSlider::handle:horizontal {{ width: 18px; height: 18px; margin: -7px 0; background: {t['bg_panel']}; border: 2px solid {t['accent']}; border-radius: 9px; }}
    QProgressBar {{ border: none; background: {t['bg_input']}; border-radius: 3px; min-height: 6px; max-height: 6px; }}
    QProgressBar::chunk {{ background: {t['accent']}; border-radius: 3px; }}
    QToolTip {{ background: {t['text_primary']}; color: {t['text_on_accent']}; border: none; border-radius: {g['radius_sm']}px; padding: 6px 10px; font-size: {g['font_xs']}px; }}
    """
