import os
from typing import Optional


class ViewerError(RuntimeError):
    """Base error with a safe message for the user and technical diagnostics."""

    code = "viewer_error"
    user_title = "Не удалось открыть файл"
    user_message = "Не удалось открыть файл. Попробуйте выбрать другой файл."

    def __init__(self, file_path: str = "", detail: str = "", cause: Optional[BaseException] = None):
        self.file_path = file_path or ""
        self.detail = detail or ""
        self.cause = cause
        filename = os.path.basename(self.file_path) if self.file_path else "неизвестный файл"
        technical = f"[{self.code}] {filename}"
        if self.detail:
            technical += f": {self.detail}"
        super().__init__(technical)


class MissingCodecError(ViewerError):
    code = "missing_codec"
    user_message = (
        "Этот медицинский снимок использует способ сжатия, который не удалось "
        "распаковать. Подробности сохранены в журнале."
    )


class CorruptFileError(ViewerError):
    code = "corrupt_file"
    user_message = (
        "Файл повреждён или загружен не полностью. Попробуйте получить его повторно "
        "или открыть другой файл."
    )


class InvalidMetadataError(ViewerError):
    code = "invalid_metadata"
    user_message = (
        "В файле отсутствуют обязательные данные медицинского снимка. "
        "Приложение не может безопасно его показать."
    )


class UnsupportedFormatError(ViewerError):
    code = "unsupported_format"
    user_message = "Этот тип файла или изображения пока не поддерживается."


class MemoryLimitError(ViewerError):
    code = "memory_limit"
    user_message = (
        "Снимок слишком большой для безопасного открытия. Закройте другие снимки "
        "или попробуйте открыть файл отдельно."
    )


class FileAccessError(ViewerError):
    code = "file_access"
    user_message = (
        "Не удалось прочитать файл. Проверьте, что он доступен и не используется "
        "другой программой."
    )


class ProcessingError(ViewerError):
    code = "processing_error"
    user_message = (
        "Не удалось подготовить изображение для показа. Подробности сохранены "
        "в журнале."
    )


def wrap_unexpected_error(exc: BaseException, file_path: str = "") -> ViewerError:
    if isinstance(exc, ViewerError):
        return exc
    if isinstance(exc, MemoryError):
        return MemoryLimitError(file_path, str(exc), exc)
    if isinstance(exc, (FileNotFoundError, PermissionError, OSError)):
        return FileAccessError(file_path, f"{type(exc).__name__}: {exc}", exc)
    return ProcessingError(file_path, f"{type(exc).__name__}: {exc}", exc)
