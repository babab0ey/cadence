"""Concise mouse and keyboard guide for a non-technical user."""

from PyQt6 import QtCore, QtWidgets
from PyQt6.QtCore import Qt

from resources.design_tokens import theme_tokens
from resources.icons import make_pixmap
from ui.dialogs.base_dialog import ClaudeDialog


class HelpRow(QtWidgets.QFrame):
    def __init__(self, icon, action, explanation, dark=False, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 7, 0, 7)
        layout.setSpacing(12)
        icon_label = QtWidgets.QLabel()
        icon_label.setFixedSize(32, 32)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setPixmap(make_pixmap(icon, theme_tokens(dark)["accent"], 22))
        layout.addWidget(icon_label)
        text = QtWidgets.QVBoxLayout()
        text.setSpacing(2)
        title = QtWidgets.QLabel(action)
        title.setWordWrap(True)
        text.addWidget(title)
        detail = QtWidgets.QLabel(explanation)
        detail.setProperty("role", "caption")
        detail.setWordWrap(True)
        text.addWidget(detail)
        layout.addLayout(text, 1)


class HelpDialog(ClaudeDialog):
    def __init__(self, parent=None):
        dark = bool(getattr(parent, "is_dark_theme", False))
        super().__init__("Как пользоваться", "Главные действия мышью и клавиатурой", dark, parent)
        self.setMinimumSize(650, 670)

        scroll = QtWidgets.QScrollArea()
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        gestures = self._section("Мышь")
        for args in (
            ("mouse", "Колёсико мыши", "Изменить масштаб снимка"),
            ("contrast", "Правая кнопка + движение ← →", "Изменить контраст"),
            ("contrast", "Правая кнопка + движение ↑ ↓", "Изменить яркость"),
            ("maximize-2", "Двойной щелчок", "Открыть снимок во весь экран или вернуться назад"),
            ("move", "Средняя кнопка или Shift + левая", "Переместить снимок"),
        ):
            gestures.layout().addWidget(HelpRow(*args, dark, gestures))
        layout.addWidget(gestures)

        keyboard = self._section("Клавиатура")
        for args in (
            ("keyboard", "Esc", "Выйти из полноэкранного просмотра"),
            ("keyboard", "Alt + колёсико", "Предыдущий или следующий кадр"),
            ("folder-open", "Ctrl + Shift + O", "Открыть папку с исследованием"),
            ("info", "Ctrl + I", "Открыть информацию о пациенте"),
        ):
            keyboard.layout().addWidget(HelpRow(*args, dark, keyboard))
        layout.addWidget(keyboard)

        measurements = self._section("Измерения и пометки")
        for args in (
            ("ruler", "Линейка", "Измерить расстояние"),
            ("drafting-compass", "Угол", "Измерить угол по трём точкам"),
            ("scan", "Область интереса", "Узнать среднее значение, отклонение, минимум и максимум"),
            ("pen-line", "Перо и заметка", "Оставить визуальную или текстовую пометку"),
        ):
            measurements.layout().addWidget(HelpRow(*args, dark, measurements))
        layout.addWidget(measurements)
        layout.addStretch()
        scroll.setWidget(body)
        self.content_layout.addWidget(scroll)
        close = self.add_footer_button("Понятно", self.accept, "primary", "check")
        close.setDefault(True)

    @staticmethod
    def _section(title):
        card = QtWidgets.QFrame()
        card.setObjectName("sectionCard")
        layout = QtWidgets.QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(2)
        heading = QtWidgets.QLabel(title)
        heading.setProperty("role", "sectionTitle")
        layout.addWidget(heading)
        return card
