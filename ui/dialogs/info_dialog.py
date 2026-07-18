"""Patient information dialog optimized for copying into documents."""

import os

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt

from resources.design_tokens import GEOMETRY, theme_tokens
from resources.icons import make_icon
from ui.dialogs.base_dialog import ClaudeDialog


class PatientField(QtWidgets.QFrame):
    copied = QtCore.pyqtSignal(str)

    def __init__(self, label, value, dark=False, parent=None):
        super().__init__(parent)
        self.label_text = str(label)
        self.value_text = str(value or "—")
        self.dark = dark
        self.setMouseTracking(True)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(8)
        column = QtWidgets.QVBoxLayout()
        column.setSpacing(2)
        label_widget = QtWidgets.QLabel(self.label_text)
        label_widget.setProperty("role", "caption")
        column.addWidget(label_widget)
        self.value_label = QtWidgets.QLabel(self.value_text)
        self.value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.value_label.setWordWrap(True)
        column.addWidget(self.value_label)
        layout.addLayout(column, 1)
        self.copy_button = QtWidgets.QToolButton()
        self.copy_button.setProperty("buttonStyle", "ghost")
        self.copy_button.setProperty("iconOnly", True)
        self.copy_button.setToolTip(f"Копировать поле «{self.label_text}»")
        self.copy_button.setIcon(make_icon("copy", theme_tokens(dark)["text_secondary"], 18))
        self.copy_button.setIconSize(QtCore.QSize(18, 18))
        self.copy_button.clicked.connect(self.copy_value)
        self.copy_button.hide()
        layout.addWidget(self.copy_button)

    def enterEvent(self, event):
        self.copy_button.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self.copy_button.hasFocus():
            self.copy_button.hide()
        super().leaveEvent(event)

    def copy_value(self):
        QtWidgets.QApplication.clipboard().setText(self.value_text)
        self.copy_button.setIcon(make_icon("check", "#4CAF82", 18))
        self.copied.emit(self.label_text)
        QtCore.QTimer.singleShot(800, self._restore_copy_icon)

    def _restore_copy_icon(self):
        self.copy_button.setIcon(make_icon("copy", theme_tokens(self.dark)["text_secondary"], 18))


class DicomInfoDialog(ClaudeDialog):
    def __init__(self, view_index, vd, current_zoom, brightness, contrast, negative_mode, is_dark_theme, parent=None):
        filename = os.path.basename(vd.file_path or "Файл не выбран")
        super().__init__(
            "Информация о пациенте",
            f"Снимок {view_index + 1} · {filename}",
            is_dark_theme,
            parent,
        )
        self.setMinimumSize(760, 650)
        self._sections = self._build_sections(vd, current_zoom, brightness, contrast, negative_mode)
        self._plain_text = self._make_plain_text()

        scroll = QtWidgets.QScrollArea()
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.viewport().setAutoFillBackground(False)
        body = QtWidgets.QWidget()
        body_layout = QtWidgets.QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(12)
        for section_name, fields in self._sections:
            body_layout.addWidget(self._section_card(section_name, fields, is_dark_theme))
        body_layout.addStretch()
        scroll.setWidget(body)
        self.content_layout.addWidget(scroll)

        close_button = self.add_footer_button("Закрыть", self.accept, "secondary")
        close_button.setToolTip("Закрыть окно информации")
        self.copy_all_button = self.add_footer_button("Копировать всё", self.copy_all, "primary", "copy")
        self.copy_all_button.setDefault(True)

    @staticmethod
    def _build_sections(vd, zoom, brightness, contrast, negative):
        return (
            ("Пациент", (
                ("ФИО", vd.patient_name),
                ("Идентификатор", vd.patient_id),
                ("Дата рождения", vd.patient_birth_date),
                ("Пол", vd.patient_sex),
            )),
            ("Исследование", (
                ("Дата", vd.study_date),
                ("Время", vd.study_time),
                ("Описание", vd.study_description),
                ("Вид исследования", vd.modality),
                ("Область тела", f"{vd.body_part} {vd.view_position}".strip()),
                ("Учреждение", vd.institution_name),
            )),
            ("Серия", (
                ("Описание серии", vd.series_description or "—"),
                ("Имя файла", os.path.basename(vd.file_path or "—")),
                ("Количество кадров", vd.number_of_frames),
                ("Размер пикселя", f"{vd.pixel_spacing:.4f} мм"),
                ("Яркость / Контраст", f"{brightness} / {contrast:.2f}"),
                ("Масштаб", f"{zoom:.2f}×"),
                ("Негатив", "Включён" if negative else "Выключен"),
            )),
            ("Оборудование", (
                ("Производитель", getattr(vd, "manufacturer", "N/A")),
                ("Модель", getattr(vd, "equipment_model", "N/A")),
                ("Рабочая станция", getattr(vd, "station_name", "N/A")),
            )),
        )

    def _section_card(self, title, fields, dark):
        card = QtWidgets.QFrame()
        card.setObjectName("sectionCard")
        layout = QtWidgets.QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)
        heading = QtWidgets.QLabel(title)
        heading.setProperty("role", "sectionTitle")
        layout.addWidget(heading)
        for label, value in fields:
            layout.addWidget(PatientField(label, value, dark, card))
        return card

    def _make_plain_text(self):
        lines = []
        for section, fields in self._sections:
            if lines:
                lines.append("")
            lines.append(section)
            lines.extend(f"{label}: {value}" for label, value in fields)
        return "\n".join(lines)

    def copy_all(self):
        QtWidgets.QApplication.clipboard().setText(self._plain_text)
        self.copy_all_button.setText("Скопировано")
        self.copy_all_button.setIcon(make_icon("check", "#FFFFFF", 20))
        QtCore.QTimer.singleShot(800, self._restore_copy_all)

    def _restore_copy_all(self):
        self.copy_all_button.setText("Копировать всё")
        self.copy_all_button.setIcon(make_icon("copy", "#FFFFFF", 20))
