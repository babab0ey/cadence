import os
import re
from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtCore import Qt
from core.utils import DICOM_EXTS, IMAGE_EXTS, PIL_AVAILABLE
from core.tasks import ThumbnailLoadTask


class ThumbnailWidget(QtWidgets.QFrame):
    """Claude-style thumbnail card: rounded, soft hover, small label."""
    fileClicked = QtCore.pyqtSignal(str)

    def __init__(self, file_path, thumbnail_pool=None, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.thumbnail_pool = thumbnail_pool or QtCore.QThreadPool.globalInstance()
        self._thumbnail_task = None
        self.setObjectName("thumbnailItem")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 8)
        layout.setSpacing(6)

        self.thumbnail_label = QtWidgets.QLabel()
        self.thumbnail_label.setObjectName("thumbnailLabel")
        self.thumbnail_label.setFixedSize(168, 168)
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_label.setScaledContents(False)
        layout.addWidget(self.thumbnail_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.filename_label = QtWidgets.QLabel(self._truncate_name(os.path.basename(self.file_path)))
        self.filename_label.setObjectName("thumbnailFilename")
        self.filename_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.filename_label.setWordWrap(False)
        self.filename_label.setMaximumWidth(168)
        layout.addWidget(self.filename_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.setAcceptDrops(True)
        self.setToolTip(file_path)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.load_thumbnail()

    @staticmethod
    def _truncate_name(name, max_len=22):
        if len(name) <= max_len:
            return name
        stem, ext = os.path.splitext(name)
        keep = max_len - len(ext) - 2
        return stem[:keep] + "…" + ext

    def load_thumbnail(self):
        ext = os.path.splitext(self.file_path)[1].lower()
        if ext in DICOM_EXTS:
            try:
                import pydicom
                ds = pydicom.dcmread(self.file_path, stop_before_pixels=True)
                modality = getattr(ds, "Modality", "DCM")
                self.thumbnail_label.setText(f"DICOM\n{modality}")
            except Exception:
                self.thumbnail_label.setText("DICOM")
        elif ext in IMAGE_EXTS and PIL_AVAILABLE:
            self.thumbnail_label.setText("Изображение")
        else:
            self.thumbnail_label.setText(ext.upper().replace(".", "") or "FILE")

        task = ThumbnailLoadTask(self.file_path, max_size=160)
        task.signals.succeeded.connect(self._on_thumbnail_loaded)
        task.signals.failed.connect(self._on_thumbnail_failed)
        self._thumbnail_task = task
        self.thumbnail_pool.start(task)

    @QtCore.pyqtSlot(str, object)
    def _on_thumbnail_loaded(self, file_path, image):
        if file_path != self.file_path or image is None or image.isNull():
            return
        pixmap = QtGui.QPixmap.fromImage(image)
        if not pixmap.isNull():
            self.thumbnail_label.setText("")
            self.thumbnail_label.setPixmap(
                pixmap.scaled(
                    160,
                    160,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        self._thumbnail_task = None

    @QtCore.pyqtSlot(str)
    def _on_thumbnail_failed(self, file_path):
        if file_path == self.file_path:
            self._thumbnail_task = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            drag = QtGui.QDrag(self)
            mime_data = QtCore.QMimeData()
            mime_data.setText(f"sidebar_file_{self.file_path}")
            drag.setMimeData(mime_data)
            pixmap = self.thumbnail_label.pixmap()
            if pixmap and not pixmap.isNull():
                drag.setPixmap(pixmap.scaled(120, 120, Qt.AspectRatioMode.KeepAspectRatio,
                                              Qt.TransformationMode.SmoothTransformation))
            drag.exec(Qt.DropAction.MoveAction)

    def dragEnterEvent(self, event):
        mime_data = event.mimeData()
        mime_text = mime_data.text() if mime_data.hasText() else ""
        if (mime_data.hasUrls() or
                (mime_text and (mime_text.startswith('main_view_file_') or mime_text.startswith('sidebar_file_')))):
            event.acceptProposedAction()
            self.setStyleSheet(
                "QWidget#thumbnailItem { background-color: rgba(217, 119, 87, 0.10);"
                "border: 1.5px solid #D97757; border-radius: 10px; }"
            )
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dropEvent(self, event):
        mime_data = event.mimeData()
        mime_text = mime_data.text() if mime_data.hasText() else ""
        if mime_text and mime_text.startswith('main_view_file_'):
            try:
                m = re.match(r'^main_view_file_(\d+)_(.+)$', mime_text)
                if m:
                    event.acceptProposedAction()
                    self.setStyleSheet("")
                    return
            except Exception:
                pass
        event.ignore()
        self.setStyleSheet("")

    def dragLeaveEvent(self, event):
        self.setStyleSheet("")


class SidebarWidget(QtWidgets.QWidget):
    fileDroppedToView = QtCore.pyqtSignal(int, str)
    viewSwapToSidebar = QtCore.pyqtSignal(int, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebarRoot")
        self._extra_files = []
        self.thumbnail_pool = QtCore.QThreadPool(self)
        self.thumbnail_pool.setMaxThreadCount(2)
        self._setup_ui()

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header ──
        header = QtWidgets.QWidget()
        header.setStyleSheet("background: transparent;")
        header_layout = QtWidgets.QVBoxLayout(header)
        header_layout.setContentsMargins(16, 14, 16, 4)
        header_layout.setSpacing(2)

        title = QtWidgets.QLabel("Studies")
        title.setStyleSheet(
            "font-family: Georgia, Charter, serif; font-size: 18px; font-weight: 500;"
            "background: transparent;"
        )
        header_layout.addWidget(title)

        self.count_label = QtWidgets.QLabel("0 files")
        self.count_label.setObjectName("mutedLabel")
        self.count_label.setStyleSheet("color: #73716C; font-size: 12px; background: transparent;")
        header_layout.addWidget(self.count_label)

        layout.addWidget(header)

        # ── Search ──
        self.search_bar = QtWidgets.QLineEdit()
        self.search_bar.setPlaceholderText("Поиск файла…")
        self.search_bar.setObjectName("sidebarSearch")
        self.search_bar.textChanged.connect(self.filter_sidebar)
        layout.addWidget(self.search_bar)

        # ── Scroll area for thumbnails ──
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setMinimumWidth(220)
        self.scroll_area.setMaximumWidth(260)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.scroll_area_widget = QtWidgets.QWidget()
        self.scroll_area_widget.setStyleSheet("background: transparent;")
        self.scroll_area_layout = QtWidgets.QVBoxLayout(self.scroll_area_widget)
        self.scroll_area_layout.setContentsMargins(8, 4, 8, 12)
        self.scroll_area_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area_layout.setSpacing(4)
        self.scroll_area.setWidget(self.scroll_area_widget)
        self.scroll_area.setWidgetResizable(True)
        layout.addWidget(self.scroll_area, stretch=1)

        # ── Empty state ──
        self.empty_state = QtWidgets.QLabel(
            "Перетащите DICOM-файлы\nили папку сюда,\nчтобы начать"
        )
        self.empty_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_state.setStyleSheet(
            "color: #8E8B82; font-size: 13px; padding: 40px 20px;"
            "background: transparent; line-height: 1.6;"
        )
        self.empty_state.setWordWrap(True)
        self.scroll_area_layout.addWidget(self.empty_state)

        self.scroll_area_widget.setAcceptDrops(True)
        self.scroll_area_widget.installEventFilter(self)

        # Default minimum width
        self.setMinimumWidth(240)
        self.setMaximumWidth(280)

    @property
    def extra_files(self):
        return self._extra_files

    @extra_files.setter
    def extra_files(self, files):
        self._extra_files = files

    def eventFilter(self, obj, event):
        if obj == self.scroll_area_widget:
            if event.type() == QtCore.QEvent.Type.DragEnter:
                return self._sidebar_drag_enter(event)
            elif event.type() == QtCore.QEvent.Type.Drop:
                return self._sidebar_drop(event)
            elif event.type() == QtCore.QEvent.Type.DragMove:
                event.acceptProposedAction()
                return True
        return super().eventFilter(obj, event)

    def _sidebar_drag_enter(self, event):
        mime_data = event.mimeData()
        if mime_data.hasText():
            mime_text = mime_data.text()
            if (mime_text.startswith('main_view_file_') or
                    mime_text.startswith('sidebar_file_') or
                    event.mimeData().hasUrls()):
                event.acceptProposedAction()
                return True
        event.ignore()
        return True

    def _sidebar_drop(self, event):
        mime_data = event.mimeData()
        mime_text = mime_data.text() if mime_data.hasText() else ""
        if mime_text.startswith('main_view_file_'):
            try:
                m = re.match(r'^main_view_file_(\d+)_(.+)$', mime_text)
                if m:
                    source_view_idx = int(m.group(1))
                    source_file_path = m.group(2)
                    self.viewSwapToSidebar.emit(source_view_idx, source_file_path)
                    event.acceptProposedAction()
                    return True
            except Exception:
                pass
        event.ignore()
        return True

    def filter_sidebar(self):
        text = self.search_bar.text().lower()
        self.update_sidebar(filter_text=text)

    def update_sidebar(self, filter_text=""):
        # Clear current items
        while self.scroll_area_layout.count() > 0:
            item = self.scroll_area_layout.takeAt(0)
            w = item.widget() if item else None
            if w and w is not self.empty_state:
                w.deleteLater()

        from core.workspace_manager import sort_files_for_mammo
        self._extra_files = sort_files_for_mammo(self._extra_files)

        # Filter
        visible_files = [
            f for f in self._extra_files
            if not filter_text or filter_text in os.path.basename(f).lower()
        ]

        # Update count
        total = len(self._extra_files)
        if filter_text:
            self.count_label.setText(f"{len(visible_files)} of {total}")
        else:
            self.count_label.setText(f"{total} file{'s' if total != 1 else ''}")

        # Show empty state if nothing
        if not visible_files:
            self.empty_state.show()
            if filter_text:
                self.empty_state.setText(f"Ничего не найдено\nпо запросу «{filter_text}»")
            else:
                self.empty_state.setText("Перетащите DICOM-файлы\nили папку сюда,\nчтобы начать")
            self.scroll_area_layout.addWidget(self.empty_state)
            return

        self.empty_state.hide()

        # Add thumbnails (limit to 200 for perf)
        limit = 200
        for file_path in visible_files[:limit]:
            thumbnail = ThumbnailWidget(file_path, self.thumbnail_pool)
            self.scroll_area_layout.addWidget(thumbnail)

        # Add a stretch at the bottom
        self.scroll_area_layout.addStretch()

    def toggle_visibility(self, toggle_handle):
        if self.isVisible():
            self.hide()
            toggle_handle.setText("▶")
        else:
            self.show()
            toggle_handle.setText("◀")
