"""Virtualized, collapsible study catalogue."""

import os
import re
from dataclasses import dataclass

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt

from core.tasks import SidebarPreviewTask
from core.workspace_manager import sort_files_for_mammo
from resources.design_tokens import GEOMETRY, STATUS, theme_tokens
from resources.icons import make_icon, make_pixmap


class StudyRoles:
    FilePathRole = int(Qt.ItemDataRole.UserRole) + 1
    PreviewRole = FilePathRole + 1
    StatusRole = FilePathRole + 2
    FrameCountRole = FilePathRole + 3
    ErrorRole = FilePathRole + 4


@dataclass
class StudyEntry:
    file_path: str
    preview: QtGui.QImage | None = None
    status: str = "idle"
    frame_count: int = 1
    error: str = ""


class StudyListModel(QtCore.QAbstractListModel):
    """A lazy model: only delegate-visible rows request decoded previews."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._entries = []
        self._row_by_path = {}
        self.thumbnail_pool = QtCore.QThreadPool(self)
        self.thumbnail_pool.setMaxThreadCount(2)
        self._tasks = {}
        self._shutting_down = False

    def rowCount(self, parent=QtCore.QModelIndex()):
        return 0 if parent.isValid() else len(self._entries)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._entries)):
            return None
        entry = self._entries[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return os.path.basename(entry.file_path)
        if role == Qt.ItemDataRole.ToolTipRole:
            return os.path.basename(entry.file_path)
        if role == StudyRoles.FilePathRole:
            return entry.file_path
        if role == StudyRoles.PreviewRole:
            return entry.preview
        if role == StudyRoles.StatusRole:
            return entry.status
        if role == StudyRoles.FrameCountRole:
            return entry.frame_count
        if role == StudyRoles.ErrorRole:
            return entry.error
        return None

    def flags(self, index):
        flags = super().flags(index)
        if index.isValid():
            flags |= Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
        return flags

    def mimeTypes(self):
        return ["text/plain"]

    def mimeData(self, indexes):
        mime = QtCore.QMimeData()
        if indexes:
            path = indexes[0].data(StudyRoles.FilePathRole)
            if path:
                mime.setText(f"sidebar_file_{path}")
        return mime

    def set_files(self, file_paths):
        self.beginResetModel()
        self._entries = [StudyEntry(path) for path in file_paths]
        self._row_by_path = {entry.file_path: row for row, entry in enumerate(self._entries)}
        self._tasks.clear()
        self.endResetModel()

    def ensure_preview(self, row):
        if self._shutting_down:
            return
        if not (0 <= row < len(self._entries)):
            return
        entry = self._entries[row]
        if entry.status != "idle":
            return
        entry.status = "loading"
        index = self.index(row, 0)
        self.dataChanged.emit(index, index, [StudyRoles.StatusRole])
        task = SidebarPreviewTask(entry.file_path, max_size=168)
        task.signals.succeeded.connect(self._preview_ready)
        task.signals.failed.connect(self._preview_failed)
        self._tasks[entry.file_path] = task
        self.thumbnail_pool.start(task)

    @QtCore.pyqtSlot(str, object, int)
    def _preview_ready(self, file_path, image, frame_count):
        if self._shutting_down:
            return
        row = self._row_by_path.get(file_path)
        self._tasks.pop(file_path, None)
        if row is None or row >= len(self._entries):
            return
        entry = self._entries[row]
        entry.preview = image
        entry.frame_count = max(1, int(frame_count or 1))
        entry.status = "ok"
        index = self.index(row, 0)
        self.dataChanged.emit(index, index)

    @QtCore.pyqtSlot(str, str)
    def _preview_failed(self, file_path, error):
        if self._shutting_down:
            return
        row = self._row_by_path.get(file_path)
        self._tasks.pop(file_path, None)
        if row is None or row >= len(self._entries):
            return
        entry = self._entries[row]
        entry.status = "error"
        entry.error = error
        index = self.index(row, 0)
        self.dataChanged.emit(index, index)

    def shutdown(self):
        """Drain preview work before the owning window is destroyed."""
        self._shutting_down = True
        self.thumbnail_pool.clear()
        if not self.thumbnail_pool.waitForDone(1000):
            self.thumbnail_pool.waitForDone(-1)
        self._tasks.clear()

    def index_for_path(self, file_path):
        row = self._row_by_path.get(file_path, -1)
        return self.index(row, 0) if row >= 0 else QtCore.QModelIndex()


class StudyFilterModel(QtCore.QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._query = ""

    def set_query(self, query):
        self._query = query.casefold().strip()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        if not self._query:
            return True
        index = self.sourceModel().index(source_row, 0, source_parent)
        return self._query in str(index.data(Qt.ItemDataRole.DisplayRole) or "").casefold()


class StudyItemDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.collapsed = False
        self.dark = False

    def sizeHint(self, option, index):
        if self.collapsed:
            return QtCore.QSize(GEOMETRY["sidebar_collapsed"], 52)
        return QtCore.QSize(max(180, option.rect.width()), 218)

    def paint(self, painter, option, index):
        source_model = index.model()
        source_index = index
        if isinstance(source_model, QtCore.QSortFilterProxyModel):
            source_index = source_model.mapToSource(index)
            source_model = source_model.sourceModel()
        if hasattr(source_model, "ensure_preview"):
            QtCore.QTimer.singleShot(0, lambda row=source_index.row(), model=source_model: model.ensure_preview(row))

        tokens = theme_tokens(self.dark)
        painter.save()
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        rect = option.rect.adjusted(2, 2, -2, -2)
        selected = bool(option.state & QtWidgets.QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QtWidgets.QStyle.StateFlag.State_MouseOver)
        if selected or hovered:
            color = QtGui.QColor(tokens["accent"] if selected else tokens["bg_hover"])
            if selected:
                color.setAlpha(28 if not self.dark else 38)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(rect, GEOMETRY["radius_md"], GEOMETRY["radius_md"])
        if selected:
            painter.setBrush(QtGui.QColor(tokens["accent"]))
            painter.drawRoundedRect(QtCore.QRectF(rect.left(), rect.top() + 8, 3, rect.height() - 16), 1.5, 1.5)

        preview = index.data(StudyRoles.PreviewRole)
        if self.collapsed:
            preview_rect = QtCore.QRect(rect.left() + 4, rect.top() + 4, 36, 36)
        else:
            side = min(168, max(80, rect.width() - 20))
            preview_rect = QtCore.QRect(rect.center().x() - side // 2, rect.top() + 7, side, 168)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QtGui.QColor(tokens["bg_input"]))
        painter.drawRoundedRect(QtCore.QRectF(preview_rect), GEOMETRY["radius_sm"], GEOMETRY["radius_sm"])
        if isinstance(preview, QtGui.QImage) and not preview.isNull():
            pixmap = QtGui.QPixmap.fromImage(preview)
            scaled = pixmap.scaled(preview_rect.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            target = QtCore.QRect(
                preview_rect.center().x() - scaled.width() // 2,
                preview_rect.center().y() - scaled.height() // 2,
                scaled.width(), scaled.height(),
            )
            clip = QtGui.QPainterPath()
            clip.addRoundedRect(QtCore.QRectF(preview_rect), GEOMETRY["radius_sm"], GEOMETRY["radius_sm"])
            painter.setClipPath(clip)
            painter.drawPixmap(target, scaled)
            painter.setClipping(False)
        else:
            placeholder = make_pixmap("file-image", tokens["text_disabled"], 30 if not self.collapsed else 18)
            painter.drawPixmap(preview_rect.center() - QtCore.QPoint(placeholder.width() // 2, placeholder.height() // 2), placeholder)

        status = str(index.data(StudyRoles.StatusRole) or "idle")
        status_icon, status_color = {
            "loading": ("loader-circle", tokens["text_secondary"]),
            "error": ("circle-alert", STATUS["error"]),
            "ok": ("circle-check", STATUS["success"]),
        }.get(status, ("loader-circle", tokens["text_disabled"]))
        status_pixmap = make_pixmap(status_icon, status_color, 16)
        painter.drawPixmap(preview_rect.right() - 18, preview_rect.top() + 4, status_pixmap)

        if not self.collapsed:
            filename_rect = QtCore.QRect(rect.left() + 12, preview_rect.bottom() + 8, rect.width() - 24, 22)
            font = painter.font()
            font.setPixelSize(GEOMETRY["font_sm"])
            font.setWeight(QtGui.QFont.Weight.Medium)
            painter.setFont(font)
            painter.setPen(QtGui.QColor(tokens["text_primary"]))
            name = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
            name = painter.fontMetrics().elidedText(name, Qt.TextElideMode.ElideMiddle, filename_rect.width())
            painter.drawText(filename_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)
            frame_count = int(index.data(StudyRoles.FrameCountRole) or 1)
            caption = f"{frame_count} кадров" if frame_count > 1 else "Снимок"
            caption_rect = QtCore.QRect(filename_rect.left(), filename_rect.bottom(), filename_rect.width(), 18)
            font.setPixelSize(GEOMETRY["font_xs"])
            font.setWeight(QtGui.QFont.Weight.Normal)
            painter.setFont(font)
            painter.setPen(QtGui.QColor(tokens["text_secondary"]))
            painter.drawText(caption_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, caption)
        painter.restore()


class StudyListView(QtWidgets.QListView):
    viewDropped = QtCore.pyqtSignal(int, str)
    externalPathsDropped = QtCore.pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("studyList")
        self.setMouseTracking(True)
        self.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def dragEnterEvent(self, event):
        text = event.mimeData().text() if event.mimeData().hasText() else ""
        if text.startswith(("main_view_file_", "sidebar_file_")) or event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dropEvent(self, event):
        text = event.mimeData().text() if event.mimeData().hasText() else ""
        match = re.match(r"^main_view_file_(\d+)_(.+)$", text)
        if match:
            self.viewDropped.emit(int(match.group(1)), match.group(2))
            event.acceptProposedAction()
            return
        if event.mimeData().hasUrls():
            paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
            if paths:
                self.externalPathsDropped.emit(paths)
                event.acceptProposedAction()
                return
        super().dropEvent(event)


class SidebarWidget(QtWidgets.QWidget):
    fileDroppedToView = QtCore.pyqtSignal(int, str)
    viewSwapToSidebar = QtCore.pyqtSignal(int, str)
    fileActivated = QtCore.pyqtSignal(str)
    collapsedChanged = QtCore.pyqtSignal(bool)
    externalPathsDropped = QtCore.pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebarRoot")
        self._extra_files = []
        self._collapsed = False
        self._expanded_width = 260
        self._dark = False
        self._width_animation = None
        self._setup_ui()

    def _setup_ui(self):
        self.setMinimumWidth(GEOMETRY["sidebar_min"])
        self.setMaximumWidth(GEOMETRY["sidebar_max"])
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header = QtWidgets.QWidget(self)
        self.header.setObjectName("sidebarHeader")
        header_layout = QtWidgets.QGridLayout(self.header)
        header_layout.setContentsMargins(16, 14, 8, 8)
        header_layout.setHorizontalSpacing(6)
        header_layout.setVerticalSpacing(0)
        self.title_label = QtWidgets.QLabel("Исследования")
        self.title_label.setProperty("role", "sectionTitle")
        header_layout.addWidget(self.title_label, 0, 0)
        self.toggle_button = QtWidgets.QToolButton()
        self.toggle_button.setProperty("buttonStyle", "ghost")
        self.toggle_button.setProperty("iconOnly", True)
        self.toggle_button.setToolTip("Свернуть панель исследований")
        self.toggle_button.clicked.connect(self.toggle_collapsed)
        header_layout.addWidget(self.toggle_button, 0, 1, 2, 1)
        self.count_label = QtWidgets.QLabel("0 файлов")
        self.count_label.setProperty("role", "caption")
        header_layout.addWidget(self.count_label, 1, 0)
        layout.addWidget(self.header)

        search_wrap = QtWidgets.QWidget()
        search_layout = QtWidgets.QHBoxLayout(search_wrap)
        search_layout.setContentsMargins(12, 4, 12, 8)
        self.search_bar = QtWidgets.QLineEdit()
        self.search_bar.setPlaceholderText("Поиск по файлам…")
        self.search_bar.setClearButtonEnabled(True)
        self._search_action = self.search_bar.addAction(QtGui.QIcon(), QtWidgets.QLineEdit.ActionPosition.LeadingPosition)
        self._search_action.setToolTip("Поиск по файлам")
        for action_button in self.search_bar.findChildren(QtWidgets.QToolButton):
            action_button.setToolTip(
                "Поиск по файлам" if action_button.defaultAction() is self._search_action else "Очистить поиск"
            )
        search_layout.addWidget(self.search_bar)
        self._search_wrap = search_wrap
        layout.addWidget(search_wrap)

        self.model = StudyListModel(self)
        self.thumbnail_pool = self.model.thumbnail_pool
        self.proxy_model = StudyFilterModel(self)
        self.proxy_model.setSourceModel(self.model)
        self.delegate = StudyItemDelegate(self)
        self.list_view = StudyListView(self)
        self.list_view.setModel(self.proxy_model)
        self.list_view.setItemDelegate(self.delegate)
        self.list_view.viewDropped.connect(self.viewSwapToSidebar)
        self.list_view.externalPathsDropped.connect(self.externalPathsDropped)
        self.list_view.doubleClicked.connect(self._activate_index)

        self.empty_widget = QtWidgets.QWidget()
        empty_layout = QtWidgets.QVBoxLayout(self.empty_widget)
        empty_layout.setContentsMargins(20, 24, 20, 24)
        empty_layout.addStretch()
        self.empty_icon = QtWidgets.QLabel()
        self.empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(self.empty_icon)
        self.empty_label = QtWidgets.QLabel("Файлы не найдены")
        self.empty_label.setProperty("role", "secondary")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        empty_layout.addWidget(self.empty_label)
        empty_layout.addStretch()

        self.stack = QtWidgets.QStackedWidget()
        self.stack.addWidget(self.list_view)
        self.stack.addWidget(self.empty_widget)
        layout.addWidget(self.stack, 1)

        self._search_timer = QtCore.QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(250)
        self._search_timer.timeout.connect(self.filter_sidebar)
        self.search_bar.textChanged.connect(lambda _text: self._search_timer.start())
        self.apply_theme(False)
        self._update_empty_state()

    @property
    def extra_files(self):
        return self._extra_files

    @extra_files.setter
    def extra_files(self, files):
        self._extra_files = list(files)

    @property
    def is_collapsed(self):
        return self._collapsed

    @property
    def expanded_width(self):
        return max(GEOMETRY["sidebar_min"], min(GEOMETRY["sidebar_max"], self._expanded_width))

    def restore_state(self, width, collapsed=False):
        self._expanded_width = max(GEOMETRY["sidebar_min"], min(GEOMETRY["sidebar_max"], int(width)))
        if collapsed:
            # Mark the restored transition as already collapsed so its stored
            # expanded width is not replaced by the splitters' startup width.
            self._collapsed = True
        self.set_collapsed(bool(collapsed), animate=False)
        if not collapsed:
            self.resize(self._expanded_width, self.height())

    def remember_current_width(self):
        if not self._collapsed and GEOMETRY["sidebar_min"] <= self.width() <= GEOMETRY["sidebar_max"]:
            self._expanded_width = self.width()

    def toggle_collapsed(self):
        self.set_collapsed(not self._collapsed, animate=True)

    def set_collapsed(self, collapsed, animate=True):
        collapsed = bool(collapsed)
        if collapsed == self._collapsed and animate:
            return
        if collapsed and not self._collapsed:
            self.remember_current_width()
        self._collapsed = collapsed
        self.title_label.setVisible(not collapsed)
        self.count_label.setVisible(not collapsed)
        self._search_wrap.setVisible(not collapsed)
        self.delegate.collapsed = collapsed
        self.list_view.setSpacing(0 if collapsed else 2)
        self.list_view.setToolTip("Файлы исследования" if collapsed else "")
        target = GEOMETRY["sidebar_collapsed"] if collapsed else self.expanded_width
        self.toggle_button.setToolTip("Развернуть панель исследований" if collapsed else "Свернуть панель исследований")
        self._update_icons()
        if not animate:
            if collapsed:
                self.setFixedWidth(target)
            else:
                self.setMinimumWidth(GEOMETRY["sidebar_min"])
                self.setMaximumWidth(GEOMETRY["sidebar_max"])
                self.resize(target, self.height())
            self.delegate.sizeHintChanged.emit(QtCore.QModelIndex())
            self.collapsedChanged.emit(collapsed)
            return

        start = self.width()
        group = QtCore.QParallelAnimationGroup(self)
        for property_name in (b"minimumWidth", b"maximumWidth"):
            animation = QtCore.QPropertyAnimation(self, property_name, group)
            animation.setStartValue(start)
            animation.setEndValue(target)
            animation.setDuration(250)
            animation.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)
            group.addAnimation(animation)
        group.finished.connect(self._finish_width_animation)
        self._width_animation = group
        group.start(QtCore.QAbstractAnimation.DeletionPolicy.KeepWhenStopped)

    def _finish_width_animation(self):
        if self._collapsed:
            self.setFixedWidth(GEOMETRY["sidebar_collapsed"])
        else:
            self.setMinimumWidth(GEOMETRY["sidebar_min"])
            self.setMaximumWidth(GEOMETRY["sidebar_max"])
        self.list_view.doItemsLayout()
        self.collapsedChanged.emit(self._collapsed)

    def toggle_visibility(self, _toggle_handle=None):
        self.toggle_collapsed()

    def update_sidebar(self, filter_text=""):
        self._extra_files = sort_files_for_mammo(self._extra_files)
        self.model.set_files(self._extra_files)
        if filter_text:
            self.search_bar.setText(filter_text)
        self.filter_sidebar()

    def filter_sidebar(self):
        query = self.search_bar.text().strip()
        self.proxy_model.set_query(query)
        visible = self.proxy_model.rowCount()
        total = self.model.rowCount()
        self.count_label.setText(
            f"{visible} из {total}" if query else f"{total} {self._file_word(total)}"
        )
        self.empty_label.setText(
            f"Ничего не найдено по запросу «{query}»" if query else "Файлы не найдены"
        )
        self._update_empty_state()

    @staticmethod
    def _file_word(count):
        if count % 10 == 1 and count % 100 != 11:
            return "файл"
        if count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
            return "файла"
        return "файлов"

    def _update_empty_state(self):
        self.stack.setCurrentWidget(self.empty_widget if self.proxy_model.rowCount() == 0 else self.list_view)

    def _activate_index(self, proxy_index):
        path = proxy_index.data(StudyRoles.FilePathRole)
        if path:
            self.fileActivated.emit(path)

    def select_file(self, file_path):
        source = self.model.index_for_path(file_path)
        if not source.isValid():
            return
        proxy = self.proxy_model.mapFromSource(source)
        if proxy.isValid():
            self.list_view.setCurrentIndex(proxy)
            self.list_view.scrollTo(proxy, QtWidgets.QAbstractItemView.ScrollHint.EnsureVisible)

    def shutdown_background_tasks(self):
        self._search_timer.stop()
        self.model.shutdown()

    def apply_theme(self, dark):
        self._dark = bool(dark)
        self.delegate.dark = self._dark
        self._update_icons()
        self.list_view.viewport().update()

    def _update_icons(self):
        tokens = theme_tokens(self._dark)
        chevron = "chevron-right" if self._collapsed else "chevron-left"
        self.toggle_button.setIcon(make_icon(chevron, tokens["text_secondary"], 20))
        self.toggle_button.setIconSize(QtCore.QSize(20, 20))
        self._search_action.setIcon(make_icon("search", tokens["text_secondary"], 18))
        self.empty_icon.setPixmap(make_pixmap("image-off", tokens["text_disabled"], 32))
