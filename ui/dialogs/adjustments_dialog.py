"""Brightness and contrast controls in the shared modal design language."""

from PyQt6 import QtCore, QtWidgets
from PyQt6.QtCore import Qt
from qfluentwidgets import Slider, SwitchButton

from ui.dialogs.base_dialog import ClaudeDialog


class AdjustmentsDialog(ClaudeDialog):
    brightnessChanged = QtCore.pyqtSignal(int)
    contrastChanged = QtCore.pyqtSignal(int)
    negativeChanged = QtCore.pyqtSignal(bool)
    valuesApplied = QtCore.pyqtSignal(int, int, bool)
    valuesReset = QtCore.pyqtSignal()

    def __init__(self, brightness, contrast, negative, is_dark_theme, parent=None):
        super().__init__(
            "Яркость и контраст",
            "Изменения сразу видны на снимке",
            is_dark_theme,
            parent,
        )
        self.setMinimumSize(560, 470)
        self._original_brightness = brightness
        self._original_contrast = contrast
        self._original_negative = negative

        card = QtWidgets.QFrame()
        card.setObjectName("sectionCard")
        card_layout = QtWidgets.QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(18)

        self.brightness_slider, self.brightness_value_label = self._slider_row(
            card_layout, "Яркость", -128, 128, brightness
        )
        self.contrast_slider, self.contrast_value_label = self._slider_row(
            card_layout, "Контраст", 1, 500, int(contrast * 100), percent=True
        )
        self.content_layout.addWidget(card)

        switches = QtWidgets.QFrame()
        switches.setObjectName("sectionCard")
        switches_layout = QtWidgets.QVBoxLayout(switches)
        switches_layout.setContentsMargins(16, 14, 16, 14)
        self.negative_check = SwitchButton()
        self.negative_check.setChecked(negative)
        self.negative_check.setOnText("Негатив включён")
        self.negative_check.setOffText("Обычное изображение")
        switches_layout.addWidget(self.negative_check)
        self.optimize_check = SwitchButton()
        self.optimize_check.setChecked(False)
        self.optimize_check.setOnText("Применять после нажатия кнопки")
        self.optimize_check.setOffText("Показывать изменения сразу")
        self.optimize_check.setToolTip("Включите на очень слабом компьютере")
        switches_layout.addWidget(self.optimize_check)
        self.content_layout.addWidget(switches)
        self.content_layout.addStretch()

        self.add_footer_button("Сбросить", self._reset_values, "ghost", "rotate-ccw")
        self.add_footer_button("Отмена", self._on_rejected, "secondary")
        apply_button = self.add_footer_button("Применить", self._on_accepted, "primary", "check")
        apply_button.setDefault(True)

        self.brightness_slider.valueChanged.connect(self._on_brightness_changed)
        self.contrast_slider.valueChanged.connect(self._on_contrast_changed)
        self.negative_check.checkedChanged.connect(self._on_negative_changed)

    @staticmethod
    def _slider_row(parent_layout, title, minimum, maximum, value, percent=False):
        row = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        heading = QtWidgets.QHBoxLayout()
        heading.addWidget(QtWidgets.QLabel(title))
        heading.addStretch()
        label = QtWidgets.QLabel(f"{value / 100:.2f}" if percent else str(value))
        label.setProperty("role", "caption")
        heading.addWidget(label)
        layout.addLayout(heading)
        slider = Slider()
        slider.setOrientation(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(value)
        layout.addWidget(slider)
        parent_layout.addWidget(row)
        return slider, label

    def _on_brightness_changed(self, value):
        self.brightness_value_label.setText(str(value))
        if not self.optimize_check.isChecked():
            self.brightnessChanged.emit(value)

    def _on_contrast_changed(self, value):
        self.contrast_value_label.setText(f"{value / 100.0:.2f}")
        if not self.optimize_check.isChecked():
            self.contrastChanged.emit(value)

    def _on_negative_changed(self, checked):
        if not self.optimize_check.isChecked():
            self.negativeChanged.emit(bool(checked))

    def _reset_values(self):
        self.brightness_slider.setValue(0)
        self.contrast_slider.setValue(100)
        self.negative_check.setChecked(False)
        if not self.optimize_check.isChecked():
            self.valuesReset.emit()

    def _on_accepted(self):
        self.valuesApplied.emit(
            self.brightness_slider.value(),
            self.contrast_slider.value(),
            self.negative_check.isChecked(),
        )
        self.accept()

    def _on_rejected(self):
        if self.optimize_check.isChecked():
            self.valuesApplied.emit(
                self._original_brightness,
                int(self._original_contrast * 100),
                self._original_negative,
            )
        self.reject()
