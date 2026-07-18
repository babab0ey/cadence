import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6 import QtWidgets, QtGui, QtCore
from ui.main_window import DICOMViewer


def main():
    # Fix encoding for stdout (Russian print statements)
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

    # High-DPI is enabled by default in PyQt6
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("Claude DICOM Viewer")
    app.setOrganizationName("Anthropic-Inspired")

    # Force Fusion style (most consistent with QSS)
    app.setStyle("Fusion")

    # Default font matching Claude's Anthropic Sans (with system fallback)
    # We use Segoe UI Variable as it's the closest stock font on Windows.
    font_candidates = [
        "Segoe UI Variable",
        "Segoe UI",
        "Inter",
        "SF Pro Text",
        "system-ui",
    ]
    available_families = set(QtGui.QFontDatabase.families())
    chosen_family = "Segoe UI"
    for family in font_candidates:
        if family in available_families:
            chosen_family = family
            break

    font = QtGui.QFont(chosen_family, 9)
    font.setHintingPreference(QtGui.QFont.HintingPreference.PreferDefaultHinting)
    font.setStyleStrategy(QtGui.QFont.StyleStrategy.PreferAntialias)
    app.setFont(font)

    # Load stylesheet
    resources_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources')
    qss_path = os.path.join(resources_dir, 'style_light.qss')
    if os.path.exists(qss_path):
        with open(qss_path, 'r', encoding='utf-8') as f:
            app.setStyleSheet(f.read())

    window = DICOMViewer()
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
