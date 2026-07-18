"""Human-readable application settings built with Fluent controls."""

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt
from qfluentwidgets import Slider, SwitchButton

from core.logging_config import get_log_file
from resources.design_tokens import GEOMETRY, theme_tokens
from resources.icons import make_icon
from ui.dialogs.base_dialog import ClaudeDialog


class SettingsSection(QtWidgets.QFrame):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setObjectName("sectionCard")
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(16, 14, 16, 14)
        self.layout.setSpacing(12)
        heading = QtWidgets.QLabel(title)
        heading.setProperty("role", "sectionTitle")
        self.layout.addWidget(heading)

    def add_row(self, title, description, control):
        row = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        text_column = QtWidgets.QVBoxLayout()
        text_column.setSpacing(2)
        text_column.addWidget(QtWidgets.QLabel(title))
        caption = QtWidgets.QLabel(description)
        caption.setProperty("role", "caption")
        caption.setWordWrap(True)
        text_column.addWidget(caption)
        layout.addLayout(text_column, 1)
        layout.addWidget(control, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.layout.addWidget(row)
        return row


class SettingsDialog(ClaudeDialog):
    settingsChanged = QtCore.pyqtSignal(dict)

    def __init__(self, app_config, parent=None):
        self.app_config = dict(app_config)
        dark = bool(self.app_config.get("dark_theme", False))
        super().__init__("Настройки", "Всё необходимое — простыми словами", dark, parent)
        self.setMinimumSize(680, 690)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QtWidgets.QWidget()
        body_layout = QtWidgets.QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(12)

        appearance = SettingsSection("Внешний вид")
        self.theme_group = QtWidgets.QButtonGroup(self)
        self.theme_group.setExclusive(True)
        theme_control = QtWidgets.QWidget()
        theme_layout = QtWidgets.QHBoxLayout(theme_control)
        theme_layout.setContentsMargins(0, 0, 0, 0)
        theme_layout.setSpacing(4)
        self.theme_buttons = {}
        current_theme = self.app_config.get("theme_mode", "dark" if dark else "light")
        for mode, label in (("light", "Светлая"), ("dark", "Тёмная"), ("auto", "Авто")):
            button = QtWidgets.QPushButton(label)
            button.setCheckable(True)
            button.setProperty("segmentSelected", mode == current_theme)
            button.setChecked(mode == current_theme)
            button.setFixedWidth({"light": 108, "dark": 98, "auto": 78}[mode])
            button.clicked.connect(lambda _checked=False, value=mode: self._select_theme(value))
            self.theme_group.addButton(button)
            self.theme_buttons[mode] = button
            theme_layout.addWidget(button)
        appearance.add_row("Тема", "Светлая, тёмная или как в Windows", theme_control)
        self.large_ui_switch = self._switch(self.app_config.get("large_ui", False))
        appearance.add_row("Крупнее элементы", "Увеличить текст и кнопки", self.large_ui_switch)
        body_layout.addWidget(appearance)

        viewer = SettingsSection("Просмотр снимков")
        self.quality_combo = QtWidgets.QComboBox()
        self.quality_combo.addItem("Высокое качество", "high")
        self.quality_combo.addItem("Сбалансированно", "balanced")
        self.quality_combo.addItem("Быстрее", "fast")
        self.quality_combo.setFixedWidth(220)
        quality = self.app_config.get("render_quality", "balanced")
        self.quality_combo.setCurrentIndex(max(0, self.quality_combo.findData(quality)))
        viewer.add_row("Качество отображения", "Баланс детализации и скорости", self.quality_combo)
        self.interpolation_switch = self._switch(self.app_config.get("smooth_interpolation", True))
        viewer.add_row("Плавное изображение", "Сглаживать снимок при изменении масштаба", self.interpolation_switch)
        self.wheel_zoom_switch = self._switch(self.app_config.get("wheel_zoom", True))
        viewer.add_row("Колёсико меняет масштаб", "Alt + колёсико по-прежнему меняет кадр", self.wheel_zoom_switch)
        body_layout.addWidget(viewer)

        controls = SettingsSection("Управление")
        sensitivity_wrap = QtWidgets.QWidget()
        sensitivity_layout = QtWidgets.QVBoxLayout(sensitivity_wrap)
        sensitivity_layout.setContentsMargins(0, 0, 0, 0)
        sensitivity_layout.setSpacing(4)
        self.sensitivity_label = QtWidgets.QLabel()
        self.sensitivity_label.setProperty("role", "caption")
        self.sensitivity_slider = Slider()
        self.sensitivity_slider.setOrientation(Qt.Orientation.Horizontal)
        self.sensitivity_slider.setRange(40, 200)
        self.sensitivity_slider.setValue(int(self.app_config.get("wl_sensitivity", 100)))
        self.sensitivity_slider.setFixedWidth(230)
        self.sensitivity_slider.valueChanged.connect(self._update_sensitivity_label)
        sensitivity_layout.addWidget(self.sensitivity_label)
        sensitivity_layout.addWidget(self.sensitivity_slider)
        self._update_sensitivity_label(self.sensitivity_slider.value())
        controls.add_row("Чувствительность яркости и контраста", "Скорость изменения при движении правой кнопкой", sensitivity_wrap)
        body_layout.addWidget(controls)

        notes = SettingsSection("Пометки")
        self.note_color = QtGui.QColor(self.app_config.get("note_color", "#D97757"))
        self.note_color_button = QtWidgets.QPushButton(self.note_color.name().upper())
        self.note_color_button.setProperty("buttonStyle", "secondary")
        self.note_color_button.clicked.connect(self._pick_color)
        self._update_color_button()
        notes.add_row("Цвет пометок", "Цвет линий, пера и заметок", self.note_color_button)
        body_layout.addWidget(notes)

        about = SettingsSection("О программе")
        version = QtWidgets.QLabel("Версия 2.0.0")
        version.setProperty("role", "secondary")
        about.add_row("Cadence", "Безопасный просмотр медицинских снимков", version)
        self.log_button = QtWidgets.QPushButton("Открыть журнал")
        self.log_button.setFixedWidth(220)
        self.log_button.setProperty("buttonStyle", "secondary")
        self.log_button.setIcon(make_icon("external-link", theme_tokens(dark)["text_primary"], 18))
        self.log_button.clicked.connect(self._open_log)
        about.add_row("Диагностика", "Журнал помогает разобраться, если файл не открылся", self.log_button)
        body_layout.addWidget(about)
        body_layout.addStretch()
        scroll.setWidget(body)
        self.content_layout.addWidget(scroll)

        self.add_footer_button("Отмена", self.reject, "secondary")
        save = self.add_footer_button("Сохранить", self._on_accepted, "primary", "check")
        save.setDefault(True)

    @staticmethod
    def _switch(checked):
        switch = SwitchButton()
        switch.setChecked(bool(checked))
        switch.setOnText("Включено")
        switch.setOffText("Выключено")
        return switch

    def _select_theme(self, selected):
        for mode, button in self.theme_buttons.items():
            button.setProperty("segmentSelected", mode == selected)
            button.style().unpolish(button)
            button.style().polish(button)

    def _selected_theme(self):
        return next((mode for mode, button in self.theme_buttons.items() if button.isChecked()), "light")

    def _update_sensitivity_label(self, value):
        wording = "спокойная" if value < 80 else "обычная" if value <= 125 else "быстрая"
        self.sensitivity_label.setText(f"{wording.capitalize()} · {value}%")

    def _pick_color(self):
        color = QtWidgets.QColorDialog.getColor(self.note_color, self, "Цвет пометок")
        if color.isValid():
            self.note_color = color
            self._update_color_button()

    def _update_color_button(self):
        self.note_color_button.setText(self.note_color.name().upper())
        self.note_color_button.setIcon(make_icon("pen-line", self.note_color.name(), 18))

    def _open_log(self):
        path = get_log_file()
        if path:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(path)))

    def _on_accepted(self):
        theme_mode = self._selected_theme()
        quality = self.quality_combo.currentData()
        self.app_config.update({
            "theme_mode": theme_mode,
            "dark_theme": theme_mode == "dark",
            "large_ui": self.large_ui_switch.isChecked(),
            "render_quality": quality,
            "low_quality": quality == "fast",
            "smooth_interpolation": self.interpolation_switch.isChecked(),
            "wheel_zoom": self.wheel_zoom_switch.isChecked(),
            "wl_sensitivity": self.sensitivity_slider.value(),
            "note_color": self.note_color.name(),
        })
        self.settingsChanged.emit(self.app_config)
        self.accept()
