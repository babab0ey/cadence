import os
from html.parser import HTMLParser
import re
from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtCore import Qt


class _TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.current_cell = ""
        self.cells_in_row = []
        self.all_rows = []
        self.in_td = False
        self.in_table = False

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self.in_table = True
        elif tag == 'td':
            self.in_td = True
            self.current_cell = ""

    def handle_endtag(self, tag):
        if tag == 'table':
            self.in_table = False
        elif tag == 'td':
            self.in_td = False
            self.cells_in_row.append(self.current_cell.strip())
        elif tag == 'tr':
            if self.cells_in_row:
                self.all_rows.append(self.cells_in_row.copy())
                self.cells_in_row = []

    def handle_data(self, data):
        if self.in_td:
            self.current_cell += data.strip() + " "


class SelectableInfoTextEdit(QtWidgets.QTextEdit):
    def __init__(self, html_content, plain_content, parent=None):
        super().__init__(parent)
        self.plain_content = plain_content
        self.setHtml(html_content)
        self.setReadOnly(True)
        self.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse |
            Qt.TextInteractionFlag.TextSelectableByKeyboard
        )

    def insertFromMimeData(self, source):
        pass

    def keyPressEvent(self, event):
        if event.matches(QtGui.QKeySequence.StandardKey.Copy):
            self._copy_selection()
            event.accept()
            return
        elif event.matches(QtGui.QKeySequence.StandardKey.SelectAll):
            self.selectAll()
            event.accept()
            return
        super().keyPressEvent(event)

    def _copy_selection(self):
        cursor = self.textCursor()
        if cursor.hasSelection():
            selected_html = cursor.selection().toHtml()
            selected_plain = self._html_to_readable_text(selected_html)
            if selected_plain.strip():
                QtWidgets.QApplication.clipboard().setText(selected_plain.strip())
        else:
            QtWidgets.QApplication.clipboard().setText(self.plain_content)

    @staticmethod
    def _html_to_readable_text(html):
        parser = _TableParser()
        section_headers = ["Информация", "Пациент", "Исследование", "Технические детали"]
        try:
            parser.feed(html)
        except Exception:
            doc = QtGui.QTextDocument()
            doc.setHtml(html)
            return doc.toPlainText()

        result_lines = []
        current_section = ""
        for row in parser.all_rows:
            if len(row) >= 2:
                field = row[0].strip()
                value = row[1].strip()
                if not field or not value:
                    continue
                is_section = any(header in field for header in section_headers)
                if is_section:
                    if result_lines and result_lines[-1].strip():
                        result_lines.append("")
                    current_section = field
                    result_lines.append(field)
                    result_lines.append("")
                    continue
                clean_field = field.rstrip(':')
                if current_section in ["Пациент", "Исследование", "Технические детали"]:
                    result_lines.append(f"  {clean_field}: {value}")
                else:
                    result_lines.append(f"{clean_field}: {value}")
            elif len(row) == 1:
                content = row[0].strip()
                if content and content not in section_headers:
                    result_lines.append(content)
        result = '\n'.join(result_lines)
        result = re.sub(r'\n{3,}', '\n\n', result)
        return result.strip()


class DicomInfoDialog(QtWidgets.QDialog):
    """Claude-styled DICOM info dialog."""

    def __init__(self, view_index, vd, current_zoom, brightness, contrast, negative_mode, is_dark_theme, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Информация \u2014 Окно {view_index + 1}")
        self.setMinimumWidth(680)
        self.setMinimumHeight(560)

        # Exact Claude color palette
        if is_dark_theme:
            bg_color = "#262624"
            card_bg = "#30302E"
            text_color = "#FAF9F5"
            header_bg = "#1F1F1D"
            section_bg = "#2A2A28"
            label_color = "#C2C0B6"
            value_color = "#FAF9F5"
            muted_color = "#8E8B82"
            accent = "#D97757"
            border_color = "rgba(250,249,245,0.08)"
        else:
            bg_color = "#FAF9F5"
            card_bg = "#FFFFFF"
            text_color = "#141413"
            header_bg = "#F0EEE6"
            section_bg = "#F7F6F0"
            label_color = "#73716C"
            value_color = "#141413"
            muted_color = "#8E8B82"
            accent = "#D97757"
            border_color = "rgba(20,20,19,0.08)"

        info_html = f"""
        <style>
            body {{
                font-family: 'Segoe UI Variable', 'Segoe UI', 'Inter', system-ui, sans-serif;
                font-size: 13px;
                color: {text_color};
                background-color: {card_bg};
                line-height: 1.6;
            }}
            h2.section-title {{
                font-family: Georgia, 'Charter', 'Source Serif Pro', serif;
                color: {accent};
                font-size: 16px;
                font-weight: 500;
                margin: 18px 0 8px 0;
                padding: 0;
                letter-spacing: -0.01em;
            }}
            h2.section-title:first-child {{ margin-top: 0; }}
            table {{
                border-collapse: collapse;
                width: 100%;
                margin-bottom: 6px;
            }}
            td {{
                padding: 7px 12px;
                vertical-align: top;
                border-bottom: 1px solid {border_color};
            }}
            tr:last-child td {{ border-bottom: none; }}
            .label {{
                font-weight: 500;
                color: {label_color};
                width: 170px;
                font-size: 12px;
            }}
            .value {{
                color: {value_color};
                font-weight: 430;
            }}
            .filename {{
                color: {accent};
                font-weight: 500;
                font-family: 'Cascadia Mono', 'Consolas', monospace;
                font-size: 12px;
            }}
        </style>

        <h2 class="section-title">Файл</h2>
        <table>
            <tr><td class="label">Имя файла</td><td class="value filename">{os.path.basename(vd.file_path or 'N/A')}</td></tr>
            <tr><td class="label">Тип</td><td class="value">{vd.file_type.upper()}</td></tr>
        </table>

        <h2 class="section-title">Пациент</h2>
        <table>
            <tr><td class="label">ФИО</td><td class="value">{vd.patient_name}</td></tr>
            <tr><td class="label">ID</td><td class="value">{vd.patient_id}</td></tr>
            <tr><td class="label">Дата рождения</td><td class="value">{vd.patient_birth_date}</td></tr>
            <tr><td class="label">Пол</td><td class="value">{vd.patient_sex}</td></tr>
        </table>

        <h2 class="section-title">Исследование</h2>
        <table>
            <tr><td class="label">Дата</td><td class="value">{vd.study_date}</td></tr>
            <tr><td class="label">Время</td><td class="value">{vd.study_time}</td></tr>
            <tr><td class="label">Описание</td><td class="value">{vd.study_description}</td></tr>
            <tr><td class="label">Модальность</td><td class="value">{vd.modality}</td></tr>
            <tr><td class="label">Часть тела</td><td class="value">{vd.body_part} ({vd.view_position})</td></tr>
            <tr><td class="label">Учреждение</td><td class="value">{vd.institution_name}</td></tr>
        </table>

        <h2 class="section-title">Технические параметры</h2>
        <table>
            <tr><td class="label">Rescale Slope</td><td class="value">{vd.rescale_slope:.4f}</td></tr>
            <tr><td class="label">Rescale Intercept</td><td class="value">{vd.rescale_intercept:.4f}</td></tr>
            <tr><td class="label">Window Center / Width</td><td class="value">{vd.wc if vd.wc is not None else 'N/A'} / {vd.ww if vd.ww is not None else 'N/A'}</td></tr>
            <tr><td class="label">Photometric</td><td class="value">{vd.photometric_interpretation}</td></tr>
            <tr><td class="label">Pixel Spacing</td><td class="value">{vd.pixel_spacing:.4f} mm/px</td></tr>
            <tr><td class="label">Текущий Zoom</td><td class="value">{current_zoom:.2f}×</td></tr>
            <tr><td class="label">Яркость / Контраст</td><td class="value">{brightness} / {contrast:.2f}</td></tr>
            <tr><td class="label">Негатив</td><td class="value">{'Включён' if negative_mode else 'Выключен'}</td></tr>
        </table>
        """

        info_text = f"""Информация — Окно {view_index + 1}

Файл:
  Имя: {os.path.basename(vd.file_path or 'N/A')}
  Тип: {vd.file_type.upper()}

Пациент:
  ФИО: {vd.patient_name}
  ID: {vd.patient_id}
  ДР: {vd.patient_birth_date}
  Пол: {vd.patient_sex}

Исследование:
  Дата: {vd.study_date}
  Время: {vd.study_time}
  Описание: {vd.study_description}
  Модальность: {vd.modality}
  Часть тела: {vd.body_part} ({vd.view_position})
  Учреждение: {vd.institution_name}

Технические параметры:
  Rescale Slope: {vd.rescale_slope:.4f}
  Rescale Intercept: {vd.rescale_intercept:.4f}
  WC/WW: {vd.wc if vd.wc is not None else 'N/A'} / {vd.ww if vd.ww is not None else 'N/A'}
  Photometric: {vd.photometric_interpretation}
  Pixel Spacing: {vd.pixel_spacing:.4f} mm/px
  Zoom: {current_zoom:.2f}x
  Яркость/Контраст: {brightness} / {contrast:.2f}
  Негатив: {'Да' if negative_mode else 'Нет'}
"""

        # Layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Title
        title = QtWidgets.QLabel(f"Окно {view_index + 1}")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)

        subtitle = QtWidgets.QLabel(os.path.basename(vd.file_path or 'No file'))
        subtitle.setObjectName("mutedLabel")
        subtitle.setStyleSheet(f"color: {muted_color}; font-size: 12px;")
        layout.addWidget(subtitle)

        # Content
        text_edit = SelectableInfoTextEdit(info_html, info_text)
        text_edit.setMinimumHeight(380)
        layout.addWidget(text_edit, stretch=1)

        # Hint
        hint_label = QtWidgets.QLabel("Выделите текст и нажмите Ctrl+C для копирования")
        hint_label.setObjectName("hintLabel")
        layout.addWidget(hint_label)

        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()

        copy_btn = QtWidgets.QPushButton("Копировать всё")
        copy_btn.setObjectName("resetButton")
        button_layout.addWidget(copy_btn)

        close_btn = QtWidgets.QPushButton("Закрыть")
        close_btn.setObjectName("primaryButton")
        close_btn.setDefault(True)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

        def copy_to_clipboard():
            QtWidgets.QApplication.clipboard().setText(info_text)
            copy_btn.setText("Скопировано ✓")
            QtCore.QTimer.singleShot(1500, lambda: copy_btn.setText("Копировать всё"))

        copy_btn.clicked.connect(copy_to_clipboard)
        close_btn.clicked.connect(self.accept)
