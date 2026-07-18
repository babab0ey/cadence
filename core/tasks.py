from PyQt6 import QtCore

from core.errors import wrap_unexpected_error
from core.image_loader import apply_adjustments_pipeline, load_generic_file, load_thumbnail_qimage
from core.logging_config import get_logger


logger = get_logger("tasks")


class FileLoadSignals(QtCore.QObject):
    succeeded = QtCore.pyqtSignal(int, object)
    failed = QtCore.pyqtSignal(int, object)


class FileLoadTask(QtCore.QRunnable):
    def __init__(
        self,
        token: int,
        file_path: str,
        frame_index: int = 0,
        brightness: int = 0,
        contrast: float = 1.0,
        negative: bool = False,
        window_level_override=None,
    ):
        super().__init__()
        self.token = token
        self.file_path = file_path
        self.frame_index = frame_index
        self.brightness = brightness
        self.contrast = contrast
        self.negative = negative
        self.window_level_override = window_level_override
        self.signals = FileLoadSignals()
        self.setAutoDelete(True)

    @QtCore.pyqtSlot()
    def run(self):
        try:
            view_data = load_generic_file(self.file_path, frame_index=self.frame_index)
            if self.window_level_override is not None:
                view_data.wc, view_data.ww = self.window_level_override
            apply_adjustments_pipeline(
                view_data,
                self.brightness,
                self.contrast,
                self.negative,
            )
            self.signals.succeeded.emit(self.token, view_data)
        except BaseException as exc:
            error = wrap_unexpected_error(exc, self.file_path)
            logger.exception("Фоновая загрузка завершилась ошибкой: %s", self.file_path)
            self.signals.failed.emit(self.token, error)


class ThumbnailLoadSignals(QtCore.QObject):
    succeeded = QtCore.pyqtSignal(str, object)
    failed = QtCore.pyqtSignal(str)


class ThumbnailLoadTask(QtCore.QRunnable):
    def __init__(self, file_path: str, max_size: int = 160):
        super().__init__()
        self.file_path = file_path
        self.max_size = max_size
        self.signals = ThumbnailLoadSignals()
        self.setAutoDelete(True)

    @QtCore.pyqtSlot()
    def run(self):
        try:
            image = load_thumbnail_qimage(self.file_path, self.max_size)
            if image is not None and not image.isNull():
                self.signals.succeeded.emit(self.file_path, image)
            else:
                self.signals.failed.emit(self.file_path)
        except BaseException:
            logger.debug("Не удалось создать превью: %s", self.file_path, exc_info=True)
            self.signals.failed.emit(self.file_path)


class SidebarPreviewSignals(QtCore.QObject):
    succeeded = QtCore.pyqtSignal(str, object, int)
    failed = QtCore.pyqtSignal(str, str)


class SidebarPreviewTask(QtCore.QRunnable):
    """Lazy sidebar preview decoder with lightweight frame metadata."""

    def __init__(self, file_path: str, max_size: int = 168):
        super().__init__()
        self.file_path = file_path
        self.max_size = max_size
        self.signals = SidebarPreviewSignals()
        self.setAutoDelete(True)

    @QtCore.pyqtSlot()
    def run(self):
        try:
            image = load_thumbnail_qimage(self.file_path, self.max_size)
            if image is None or image.isNull():
                raise ValueError("Превью не создано")
            frame_count = 1
            try:
                import os
                from core.utils import DICOM_EXTS
                if os.path.splitext(self.file_path)[1].lower() in DICOM_EXTS:
                    import pydicom
                    header = pydicom.dcmread(
                        self.file_path,
                        stop_before_pixels=True,
                        specific_tags=["NumberOfFrames"],
                        force=True,
                    )
                    frame_count = max(1, int(getattr(header, "NumberOfFrames", 1) or 1))
            except Exception:
                logger.debug("Не удалось прочитать число кадров: %s", self.file_path, exc_info=True)
            self.signals.succeeded.emit(self.file_path, image, frame_count)
        except BaseException as exc:
            logger.debug("Не удалось создать превью: %s", self.file_path, exc_info=True)
            self.signals.failed.emit(self.file_path, str(exc))
