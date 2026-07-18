from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtCore import Qt


class HelpDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Справка")
        self.setMinimumWidth(560)
        self.setMinimumHeight(520)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        title = QtWidgets.QLabel("Claude DICOM Viewer")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)

        subtitle = QtWidgets.QLabel("Премиальный медицинский просмотрщик в стиле Anthropic")
        subtitle.setStyleSheet("color: #73716C; font-size: 12px;")
        layout.addWidget(subtitle)

        help_text = QtWidgets.QTextEdit()
        help_text.setReadOnly(True)
        help_text.setHtml("""
        <style>
            body {
                font-family: 'Segoe UI Variable', 'Segoe UI', system-ui, sans-serif;
                font-size: 13px;
                line-height: 1.65;
            }
            h2 {
                color: #D97757;
                font-family: Georgia, 'Charter', serif;
                font-size: 17px;
                font-weight: 500;
                margin: 16px 0 6px 0;
                letter-spacing: -0.01em;
            }
            h2:first-child { margin-top: 0; }
            h3 {
                font-family: Georgia, 'Charter', serif;
                font-size: 14px;
                font-weight: 500;
                margin: 10px 0 4px 0;
            }
            table { border-collapse: collapse; width: 100%; margin: 4px 0; }
            td { padding: 4px 10px; vertical-align: top; }
            td:first-child { width: 180px; }
            .key {
                font-family: 'Cascadia Mono', 'Consolas', monospace;
                font-size: 11px;
                background-color: rgba(217, 119, 87, 0.12);
                color: #D97757;
                border: 1px solid rgba(217, 119, 87, 0.20);
                border-radius: 5px;
                padding: 2px 8px;
                font-weight: 500;
            }
            ul { margin: 4px 0 8px 0; padding-left: 20px; }
            li { margin: 3px 0; }
            b { font-weight: 600; }
        </style>

        <h2>Горячие клавиши</h2>
        <table>
            <tr><td><span class="key">Ctrl + O</span></td><td>Открыть файл</td></tr>
            <tr><td><span class="key">Ctrl + Shift + O</span></td><td>Открыть папку</td></tr>
            <tr><td><span class="key">Ctrl + S</span></td><td>Экспортировать как изображение</td></tr>
            <tr><td><span class="key">Ctrl + I</span></td><td>DICOM информация</td></tr>
            <tr><td><span class="key">Ctrl + Z</span></td><td>Отменить действие</td></tr>
            <tr><td><span class="key">Ctrl + R</span></td><td>Повернуть на 90°</td></tr>
            <tr><td><span class="key">Ctrl + H</span></td><td>Отразить горизонтально</td></tr>
            <tr><td><span class="key">Ctrl + V</span></td><td>Отразить вертикально</td></tr>
            <tr><td><span class="key">Ctrl + +</span></td><td>Увеличить</td></tr>
            <tr><td><span class="key">Ctrl + -</span></td><td>Уменьшить</td></tr>
            <tr><td><span class="key">Ctrl + 0</span></td><td>Сбросить масштаб</td></tr>
            <tr><td><span class="key">F11</span></td><td>Системный полноэкранный режим</td></tr>
            <tr><td><span class="key">Esc</span></td><td>Выйти из одиночного просмотра или сбросить инструмент</td></tr>
            <tr><td><span class="key">Alt + R</span></td><td>Инструмент: Рулетка</td></tr>
            <tr><td><span class="key">Alt + A</span></td><td>Инструмент: Угол</td></tr>
            <tr><td><span class="key">Alt + O</span></td><td>Инструмент: ROI прямоугольник</td></tr>
            <tr><td><span class="key">Alt + P</span></td><td>Инструмент: Ручка</td></tr>
            <tr><td><span class="key">Alt + N</span></td><td>Инструмент: Заметка</td></tr>
        </table>

        <h2>Навигация</h2>
        <ul>
            <li><b>Колесо мыши</b> — зум от курсора</li>
            <li><b>Alt + колесо мыши</b> — предыдущий или следующий кадр многокадрового снимка</li>
            <li><b>Правая кнопка + движение</b> — яркость и контраст: по горизонтали контраст, по вертикали яркость</li>
            <li><b>Средняя кнопка + движение</b> — перемещение снимка</li>
            <li><b>Shift + левая кнопка + движение</b> — перемещение снимка</li>
            <li><b>Двойной клик по снимку</b> — одиночный просмотр; повторный двойной клик или Esc — выйти</li>
            <li><b>Drag &amp; Drop</b> — обмен изображениями между окнами и боковой панелью</li>
        </ul>

        <h2>Многокадровые снимки</h2>
        <ul>
            <li>Если файл содержит несколько кадров, внизу снимка появятся кнопки и слайдер.</li>
            <li>Текущий номер показан рядом: например, <b>Кадр 3 / 47</b>.</li>
        </ul>

        <h2>Измерения</h2>
        <ul>
            <li><b>Рулетка</b> — измерение расстояния в мм/px</li>
            <li><b>Угол</b> — измерение угла по трём точкам</li>
            <li><b>ROI</b> — статистика области: Mean, StdDev, Min, Max, Area</li>
        </ul>

        <h2>Пресеты Window/Level</h2>
        <table>
            <tr><td><b>Лёгкие</b></td><td>WC: −600, WW: 1500</td></tr>
            <tr><td><b>Кости</b></td><td>WC: 400, WW: 1800</td></tr>
            <tr><td><b>Мозг</b></td><td>WC: 40, WW: 80</td></tr>
            <tr><td><b>Мягкие ткани</b></td><td>WC: 40, WW: 400</td></tr>
            <tr><td><b>Печень</b></td><td>WC: 60, WW: 150</td></tr>
            <tr><td><b>Средостение</b></td><td>WC: 50, WW: 350</td></tr>
        </table>

        <h2>Поддерживаемые форматы</h2>
        <ul>
            <li><b>DICOM</b>: .dcm, .dicom, .ima, .img</li>
            <li><b>Изображения</b>: .png, .jpg, .jpeg, .bmp, .tif, .tiff</li>
            <li><b>Данные</b>: .json</li>
        </ul>
        """)
        layout.addWidget(help_text, stretch=1)

        close_btn = QtWidgets.QPushButton("Закрыть")
        close_btn.setObjectName("primaryButton")
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)

        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)
