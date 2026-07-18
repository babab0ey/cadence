import logging
import os
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


LOGGER_NAME = "claude_dicom_viewer"
MAX_LOG_BYTES = 2 * 1024 * 1024
BACKUP_COUNT = 5

_configured = False
_log_file: Optional[Path] = None
_dialog_active = False
_dialog_bridge = None


def _application_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def _fallback_log_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "ClaudeDICOMViewer" / "logs"
    return Path.home() / ".claude_dicom_viewer" / "logs"


def _prepare_log_dir() -> Path:
    for candidate in (_application_root() / "logs", _fallback_log_dir()):
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / ".write_test"
            probe.touch(exist_ok=True)
            probe.unlink(missing_ok=True)
            return candidate
        except OSError:
            continue
    raise OSError("Не удалось создать папку для журнала ошибок")


def setup_logging() -> Path:
    global _configured, _log_file
    if _configured and _log_file is not None:
        return _log_file

    log_dir = _prepare_log_dir()
    _log_file = log_dir / "dicom_viewer.log"

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(threadName)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = RotatingFileHandler(
        _log_file,
        maxBytes=MAX_LOG_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    _configured = True
    logger.info("Журнал приложения запущен: %s", _log_file)
    return _log_file


def get_logger(component: str = "") -> logging.Logger:
    setup_logging()
    name = LOGGER_NAME if not component else f"{LOGGER_NAME}.{component}"
    return logging.getLogger(name)


def get_log_file() -> Optional[Path]:
    return _log_file


def _show_unhandled_error_dialog() -> None:
    global _dialog_active
    if _dialog_active:
        return
    _dialog_active = True
    try:
        from PyQt6 import QtWidgets

        QtWidgets.QMessageBox.critical(
            None,
            "Не удалось выполнить действие",
            "Не удалось открыть файл. Подробности сохранены в журнале. "
            "Попробуйте другой файл.",
        )
    finally:
        _dialog_active = False


def install_exception_hooks() -> None:
    global _dialog_bridge
    logger = get_logger("unhandled")
    previous_hook = sys.excepthook

    try:
        from PyQt6 import QtCore, QtWidgets

        if QtWidgets.QApplication.instance() is not None:
            class DialogBridge(QtCore.QObject):
                requested = QtCore.pyqtSignal()

            _dialog_bridge = DialogBridge()
            _dialog_bridge.requested.connect(
                _show_unhandled_error_dialog,
                QtCore.Qt.ConnectionType.QueuedConnection,
            )
    except Exception:
        logger.exception("Не удалось подготовить диалог необработанной ошибки")

    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            previous_hook(exc_type, exc_value, exc_traceback)
            return
        logger.critical(
            "Необработанное исключение",
            exc_info=(exc_type, exc_value, exc_traceback),
        )
        try:
            if _dialog_bridge is not None:
                _dialog_bridge.requested.emit()
        except Exception:
            logger.exception("Не удалось показать диалог необработанной ошибки")

    def handle_thread_exception(args):
        handle_exception(args.exc_type, args.exc_value, args.exc_traceback)

    sys.excepthook = handle_exception
    threading.excepthook = handle_thread_exception
