"""Reusable premium modal surface with a quiet Claude-like entrance."""

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt

from resources.design_tokens import GEOMETRY, apply_soft_shadow, theme_tokens
from resources.icons import make_icon
from resources.interactions import install_button_interactions


class _ModalBackdrop(QtWidgets.QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("modalBackdrop")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._opacity = 0.0

    @QtCore.pyqtProperty(float)
    def backdropOpacity(self):
        return self._opacity

    @backdropOpacity.setter
    def backdropOpacity(self, value):
        self._opacity = float(value)
        self.update()

    def paintEvent(self, _event):
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), QtGui.QColor(0, 0, 0, round(102 * self._opacity)))


class ClaudeDialog(QtWidgets.QDialog):
    """Frameless dialog with rounded surface, shadow, backdrop and fade/slide."""

    def __init__(self, title, subtitle="", dark=False, parent=None):
        super().__init__(parent)
        self.dark = bool(dark)
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setWindowOpacity(0.0)
        self._animation = None
        self._backdrop = None

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(28, 28, 28, 28)
        self.surface = QtWidgets.QFrame()
        self.surface.setObjectName("dialogSurface")
        outer.addWidget(self.surface)
        apply_soft_shadow(self.surface, self.dark, blur=40, y_offset=12)

        surface_layout = QtWidgets.QVBoxLayout(self.surface)
        surface_layout.setContentsMargins(0, 0, 0, 0)
        surface_layout.setSpacing(0)

        header = QtWidgets.QWidget()
        header_layout = QtWidgets.QHBoxLayout(header)
        header_layout.setContentsMargins(24, 22, 16, 8)
        header_layout.setSpacing(12)
        title_column = QtWidgets.QVBoxLayout()
        title_column.setSpacing(4)
        self.title_label = QtWidgets.QLabel(title)
        self.title_label.setObjectName("dialogTitle")
        title_column.addWidget(self.title_label)
        self.subtitle_label = QtWidgets.QLabel(subtitle)
        self.subtitle_label.setProperty("role", "secondary")
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setVisible(bool(subtitle))
        title_column.addWidget(self.subtitle_label)
        header_layout.addLayout(title_column, 1)
        self.close_button = QtWidgets.QToolButton()
        self.close_button.setProperty("buttonStyle", "ghost")
        self.close_button.setProperty("iconOnly", True)
        self.close_button.setToolTip("Закрыть")
        self.close_button.setIcon(make_icon("x", theme_tokens(self.dark)["text_secondary"], 20))
        self.close_button.setIconSize(QtCore.QSize(20, 20))
        self.close_button.clicked.connect(self.reject)
        header_layout.addWidget(self.close_button, alignment=Qt.AlignmentFlag.AlignTop)
        surface_layout.addWidget(header)

        self.content = QtWidgets.QWidget()
        self.content_layout = QtWidgets.QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(24, 12, 24, 16)
        self.content_layout.setSpacing(16)
        surface_layout.addWidget(self.content, 1)

        self.footer = QtWidgets.QWidget()
        self.footer_layout = QtWidgets.QHBoxLayout(self.footer)
        self.footer_layout.setContentsMargins(24, 8, 24, 24)
        self.footer_layout.setSpacing(8)
        self.footer_layout.addStretch(1)
        surface_layout.addWidget(self.footer)

    def add_footer_button(self, text, callback, style="secondary", icon=""):
        button = QtWidgets.QPushButton(text)
        button.setProperty("buttonStyle", style)
        if icon:
            color = "#FFFFFF" if style == "primary" else theme_tokens(self.dark)["text_primary"]
            button.setIcon(make_icon(icon, color, 20))
            button.setIconSize(QtCore.QSize(20, 20))
        button.clicked.connect(callback)
        self.footer_layout.addWidget(button)
        return button

    def showEvent(self, event):
        install_button_interactions(self, self.dark)
        self._show_backdrop()
        final_geometry = self.geometry()
        start_geometry = QtCore.QRect(final_geometry)
        start_geometry.translate(0, -12)
        opacity = QtCore.QPropertyAnimation(self, b"windowOpacity")
        opacity.setStartValue(0.0)
        opacity.setEndValue(1.0)
        geometry = QtCore.QPropertyAnimation(self, b"geometry")
        geometry.setStartValue(start_geometry)
        geometry.setEndValue(final_geometry)
        group = QtCore.QParallelAnimationGroup(self)
        for animation in (opacity, geometry):
            animation.setDuration(250)
            animation.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)
            group.addAnimation(animation)
        self._animation = group
        group.start()
        super().showEvent(event)

    def done(self, result):
        self._hide_backdrop()
        super().done(result)

    def _show_backdrop(self):
        parent = self.parentWidget()
        if parent is None:
            return
        host = parent.centralWidget() if isinstance(parent, QtWidgets.QMainWindow) else parent
        self._backdrop = _ModalBackdrop(host)
        self._backdrop.setGeometry(host.rect())
        self._backdrop.show()
        self._backdrop.raise_()
        animation = QtCore.QPropertyAnimation(self._backdrop, b"backdropOpacity", self._backdrop)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setDuration(GEOMETRY["transition_base"])
        animation.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)
        self._backdrop._animation = animation
        animation.start()

    def _hide_backdrop(self):
        if self._backdrop is not None:
            self._backdrop.hide()
            self._backdrop.deleteLater()
            self._backdrop = None
