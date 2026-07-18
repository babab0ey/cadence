from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtCore import Qt


class SettingsDialog(QtWidgets.QDialog):
    settingsChanged = QtCore.pyqtSignal(dict)

    def __init__(self, app_config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.setMinimumWidth(440)
        self.app_config = dict(app_config)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        title = QtWidgets.QLabel("Настройки приложения")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)

        subtitle = QtWidgets.QLabel("Персонализируйте интерфейс под себя")
        subtitle.setStyleSheet("color: #73716C; font-size: 12px;")
        layout.addWidget(subtitle)

        layout.addSpacing(8)

        # ── Appearance group ──
        appearance_label = QtWidgets.QLabel("Внешний вид")
        appearance_label.setObjectName("sectionLabel")
        layout.addWidget(appearance_label)

        self.dark_theme_check = QtWidgets.QCheckBox("Тёмная тема")
        self.dark_theme_check.setChecked(self.app_config.get('dark_theme', False))
        layout.addWidget(self.dark_theme_check)

        self.large_ui_check = QtWidgets.QCheckBox("Крупный интерфейс")
        self.large_ui_check.setChecked(self.app_config.get('large_ui', False))
        layout.addWidget(self.large_ui_check)

        layout.addSpacing(8)

        # ── Performance group ──
        perf_label = QtWidgets.QLabel("Производительность")
        perf_label.setObjectName("sectionLabel")
        layout.addWidget(perf_label)

        self.low_quality_check = QtWidgets.QCheckBox("Низкое качество рендеринга (быстрее)")
        self.low_quality_check.setChecked(self.app_config.get('low_quality', False))
        layout.addWidget(self.low_quality_check)

        layout.addSpacing(8)

        # ── Annotation group ──
        ann_label = QtWidgets.QLabel("Аннотации")
        ann_label.setObjectName("sectionLabel")
        layout.addWidget(ann_label)

        color_row = QtWidgets.QHBoxLayout()
        color_row.setSpacing(10)
        color_lbl = QtWidgets.QLabel("Цвет заметок")
        color_row.addWidget(color_lbl)
        color_row.addStretch()
        self.note_color_button = QtWidgets.QPushButton()
        self.note_color_button.setFixedSize(80, 28)
        self.note_color_button.clicked.connect(self._pick_color)
        self._note_color = QtGui.QColor(self.app_config.get('note_color', '#D97757'))
        self._update_color_button()
        color_row.addWidget(self.note_color_button)
        layout.addLayout(color_row)

        layout.addStretch()

        # ── Buttons ──
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QtWidgets.QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        ok_btn = QtWidgets.QPushButton("Сохранить")
        ok_btn.setObjectName("primaryButton")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self._on_accepted)
        button_layout.addWidget(ok_btn)

        layout.addLayout(button_layout)

    def _pick_color(self):
        color = QtWidgets.QColorDialog.getColor(self._note_color, self, "Выберите цвет заметок")
        if color.isValid():
            self._note_color = color
            self._update_color_button()

    def _update_color_button(self):
        text_color = "#FFFFFF" if self._note_color.lightness() < 128 else "#141413"
        self.note_color_button.setStyleSheet(
            f"background-color: {self._note_color.name()}; color: {text_color};"
            f"border: 1px solid rgba(20,20,19,0.10); border-radius: 6px;"
            f"font-family: 'Cascadia Mono', monospace; font-size: 11px;"
        )
        self.note_color_button.setText(self._note_color.name().upper())

    def _on_accepted(self):
        self.app_config['dark_theme'] = self.dark_theme_check.isChecked()
        self.app_config['large_ui'] = self.large_ui_check.isChecked()
        self.app_config['low_quality'] = self.low_quality_check.isChecked()
        self.app_config['note_color'] = self._note_color.name()
        self.settingsChanged.emit(self.app_config)
        self.accept()
