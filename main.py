import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6 import QtGui, QtWidgets

from core.logging_config import get_logger, install_exception_hooks, setup_logging
from resources.design_tokens import GEOMETRY, build_stylesheet, register_inter_font
from ui.main_window import DICOMViewer


def application_icon() -> QtGui.QIcon:
    """Return the bundled Cadence icon in source and PyInstaller builds."""
    icon_path = Path(__file__).resolve().parent / "resources" / "cadence.png"
    return QtGui.QIcon(str(icon_path))


def main():
    log_file = setup_logging()
    logger = get_logger("main")
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    app = QtWidgets.QApplication(sys.argv)
    install_exception_hooks()
    app.setApplicationDisplayName("Cadence")
    app.setApplicationName("Claude DICOM Viewer")
    app.setOrganizationName("Anthropic-Inspired")
    icon = application_icon()
    app.setWindowIcon(icon)

    # Gives Windows one stable taskbar identity and makes the bundled icon
    # available in task switching and pinned shortcuts.
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "Cadence.DICOMViewer.2"
            )
        except (AttributeError, OSError):
            logger.debug("Не удалось установить Windows AppUserModelID", exc_info=True)

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
    window.setWindowIcon(icon)
    window.show()

    logger.info("Приложение запущено; журнал: %s", log_file)
    app.aboutToQuit.connect(lambda: logger.info("Приложение завершает работу"))

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
