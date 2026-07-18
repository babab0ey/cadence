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
