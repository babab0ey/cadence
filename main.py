import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6 import QtWidgets, QtGui, QtCore
from core.logging_config import get_logger, install_exception_hooks, setup_logging
from resources.design_tokens import GEOMETRY, build_stylesheet, register_inter_font
from ui.main_window import DICOMViewer


def main():
    log_file = setup_logging()
    logger = get_logger("main")
    # Fix encoding for stdout (Russian print statements)
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

    # High-DPI is enabled by default in PyQt6
    app = QtWidgets.QApplication(sys.argv)
    install_exception_hooks()
    app.setApplicationName("Claude DICOM Viewer")
    app.setOrganizationName("Anthropic-Inspired")

    # Fusion gives deterministic widget geometry; the visual language itself is
    # generated from resources/design_tokens.py.
    app.setStyle("Fusion")

    chosen_family = register_inter_font()
    font = QtGui.QFont(chosen_family)
    font.setPixelSize(GEOMETRY["font_base"])
    font.setHintingPreference(QtGui.QFont.HintingPreference.PreferDefaultHinting)
    font.setStyleStrategy(QtGui.QFont.StyleStrategy.PreferAntialias)
    app.setFont(font)
    app.setStyleSheet(build_stylesheet(False))

    window = DICOMViewer()
    window.show()

    logger.info("Приложение запущено; журнал: %s", log_file)
    app.aboutToQuit.connect(lambda: logger.info("Приложение завершает работу"))

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
