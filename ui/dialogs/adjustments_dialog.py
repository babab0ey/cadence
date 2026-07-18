from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtCore import Qt


class AdjustmentsDialog(QtWidgets.QDialog):
    """Claude-styled brightness/contrast/negative adjustments."""
    brightnessChanged = QtCore.pyqtSignal(int)
    contrastChanged = QtCore.pyqtSignal(int)
    negativeChanged = QtCore.pyqtSignal(bool)
    valuesApplied = QtCore.pyqtSignal(int, int, bool)
    valuesReset = QtCore.pyqtSignal()

    def __init__(self, brightness, contrast, negative, is_dark_theme, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Яркость и контраст")
        self.setMinimumWidth(460)
        self._original_brightness = brightness
        self._original_contrast = contrast
        self._original_negative = negative

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # ── Title ──
        title = QtWidgets.QLabel("Настройки изображения")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)

        subtitle = QtWidgets.QLabel("Регулируйте яркость, контраст и инвертирование изображения")
        subtitle.setObjectName("mutedLabel")
        subtitle.setStyleSheet("color: #73716C; font-size: 12px;")
        layout.addWidget(subtitle)

        layout.addSpacing(4)

        # ── Brightness slider with label ──
        brightness_row = QtWidgets.QVBoxLayout()
        brightness_row.setSpacing(6)
        bh = QtWidgets.QHBoxLayout()
        bh.addWidget(self._make_label("Яркость"))
        bh.addStretch()
        self.brightness_value_label = QtWidgets.QLabel(str(brightness))
        self.brightness_value_label.setStyleSheet(
            "color: #D97757; font-weight: 600; font-size: 13px;"
            "font-family: 'Cascadia Mono', 'Consolas', monospace;"
        )
        self.brightness_value_label.setMinimumWidth(48)
        self.brightness_value_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        bh.addWidget(self.brightness_value_label)
        brightness_row.addLayout(bh)

        self.brightness_slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setRange(-128, 128)
        self.brightness_slider.setValue(brightness)
        self.brightness_slider.setObjectName("adjustmentSlider")
        brightness_row.addWidget(self.brightness_slider)
        layout.addLayout(brightness_row)

        # ── Contrast slider ──
        contrast_row = QtWidgets.QVBoxLayout()
        contrast_row.setSpacing(6)
        ch = QtWidgets.QHBoxLayout()
        ch.addWidget(self._make_label("Контраст"))
        ch.addStretch()
        self.contrast_value_label = QtWidgets.QLabel(f"{contrast:.2f}")
        self.contrast_value_label.setStyleSheet(
            "color: #D97757; font-weight: 600; font-size: 13px;"
            "font-family: 'Cascadia Mono', 'Consolas', monospace;"
        )
        self.contrast_value_label.setMinimumWidth(48)
        self.contrast_value_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        ch.addWidget(self.contrast_value_label)
        contrast_row.addLayout(ch)

        self.contrast_slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.contrast_slider.setRange(1, 500)
        self.contrast_slider.setValue(int(contrast * 100))
        self.contrast_slider.setObjectName("adjustmentSlider")
        contrast_row.addWidget(self.contrast_slider)
        layout.addLayout(contrast_row)

        layout.addSpacing(4)

        # ── Checkboxes ──
        self.negative_check = QtWidgets.QCheckBox("Негатив (инвертировать цвета)")
        self.negative_check.setChecked(negative)
        layout.addWidget(self.negative_check)

        self.optimize_check = QtWidgets.QCheckBox("Применять изменения только при нажатии OK")
        self.optimize_check.setChecked(False)
        self.optimize_check.setToolTip("Включите для большой производительности на слабых ПК")
        layout.addWidget(self.optimize_check)

        layout.addSpacing(10)

        # ── Buttons row ──
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.setSpacing(8)

        reset_button = QtWidgets.QPushButton("Сбросить")
        reset_button.setObjectName("resetButton")
        reset_button.clicked.connect(self._reset_values)
        reset_button.setToolTip("Восстановить значения по умолчанию")
        button_layout.addWidget(reset_button)

        button_layout.addStretch()

        cancel_btn = QtWidgets.QPushButton("Отмена")
        cancel_btn.clicked.connect(self._on_rejected)
        button_layout.addWidget(cancel_btn)

        ok_btn = QtWidgets.QPushButton("Применить")
        ok_btn.setObjectName("primaryButton")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self._on_accepted)
        button_layout.addWidget(ok_btn)

        layout.addLayout(button_layout)

        # Signals
        self.brightness_slider.valueChanged.connect(self._on_brightness_changed)
        self.contrast_slider.valueChanged.connect(self._on_contrast_changed)
        self.negative_check.stateChanged.connect(self._on_negative_changed)

    @staticmethod
    def _make_label(text):
        label = QtWidgets.QLabel(text)
        label.setStyleSheet("font-weight: 500; color: inherit; font-size: 13px;")
        return label

    def _on_brightness_changed(self, value):
        self.brightness_value_label.setText(str(value))
        if not self.optimize_check.isChecked():
            self.brightnessChanged.emit(value)

    def _on_contrast_changed(self, value):
        self.contrast_value_label.setText(f"{value / 100.0:.2f}")
        if not self.optimize_check.isChecked():
            self.contrastChanged.emit(value)

    def _on_negative_changed(self, state):
        checked = self.negative_check.isChecked()
        if not self.optimize_check.isChecked():
            self.negativeChanged.emit(checked)

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
            self.negative_check.isChecked()
        )
        self.accept()

    def _on_rejected(self):
        if self.optimize_check.isChecked():
            self.valuesApplied.emit(
                self._original_brightness,
                int(self._original_contrast * 100),
                self._original_negative
            )
        self.reject()
