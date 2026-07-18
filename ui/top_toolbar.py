"""Responsive two-priority toolbar for the DICOM viewer."""

from dataclasses import dataclass

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt
from qfluentwidgets import RoundMenu

from core.utils import DICOM_PRESETS
from resources.design_tokens import GEOMETRY, theme_tokens
from resources.icons import make_icon
from tools.tool_manager import ToolManager


# Safety invariant: patient information is deliberately the first permanent
# action.  New toolbar actions must never be inserted before it or move it into
# the overflow menu — this is a clinical workflow requirement.
PERMANENT_PRIMARY_ORDER = (
    "info",
    "open_folder",
    "adjustments",
    "zoom",
    "focus",
)
assert PERMANENT_PRIMARY_ORDER[0] == "info"


@dataclass(frozen=True)
class _ActionSpec:
    action_id: str
    icon: str
    text: str
    tooltip: str
    shortcut: str = ""
    tool_id: str = ""


PRIMARY_SPECS = {
    "info": _ActionSpec("info", "info", "Инфо о пациенте", "Информация о пациенте (Ctrl+I)", "Ctrl+I"),
    "open_folder": _ActionSpec("open_folder", "folder-open", "Открыть папку", "Открыть папку с исследованием (Ctrl+Shift+O)", "Ctrl+Shift+O"),
    "adjustments": _ActionSpec("adjustments", "contrast", "Яркость / Контраст", "Настроить яркость и контраст снимка"),
    "zoom": _ActionSpec("zoom", "zoom-in", "Масштаб", "Изменить масштаб снимка"),
    "focus": _ActionSpec("focus", "maximize-2", "Во весь экран", "Полноэкранный просмотр (F11)", "F11"),
}

SECONDARY_SPECS = (
    _ActionSpec("undo", "undo-2", "Отменить", "Отменить последнее действие (Ctrl+Z)", "Ctrl+Z"),
    _ActionSpec("redo", "redo-2", "Повторить", "Повторить отменённое действие (Ctrl+Y)", "Ctrl+Y"),
    _ActionSpec("flip_h", "flip-horizontal-2", "Отразить по горизонтали", "Отразить снимок по горизонтали", "Ctrl+H"),
    _ActionSpec("flip_v", "flip-vertical-2", "Отразить по вертикали", "Отразить снимок по вертикали", "Ctrl+V"),
    _ActionSpec("rotate", "rotate-cw", "Повернуть", "Повернуть снимок на 90°", "Ctrl+R"),
    _ActionSpec("toggle_theme", "moon", "Сменить тему", "Переключить светлую и тёмную тему"),
    _ActionSpec("settings", "settings", "Настройки", "Открыть настройки"),
    _ActionSpec("export", "save", "Сохранить снимок", "Сохранить снимок как изображение", "Ctrl+S"),
    _ActionSpec("tool_ruler", "ruler", "Линейка", "Измерить расстояние", "Alt+R", ToolManager.TOOL_RULER),
    _ActionSpec("tool_angle", "drafting-compass", "Угол", "Измерить угол", "Alt+A", ToolManager.TOOL_ANGLE),
    _ActionSpec("tool_roi", "scan", "Область интереса", "Измерить область интереса", "Alt+O", ToolManager.TOOL_ROI),
    _ActionSpec("tool_pen", "pen-line", "Перо", "Нарисовать пометку", "Alt+P", ToolManager.TOOL_PEN),
    _ActionSpec("tool_note", "notebook-pen", "Заметка", "Добавить текстовую заметку", "Alt+N", ToolManager.TOOL_NOTE),
    _ActionSpec("clear_drawings", "eraser", "Стереть пометки", "Стереть пометки со всех снимков"),
    _ActionSpec("clear_all", "trash-2", "Очистить всё", "Закрыть исследование и очистить снимки только в приложении"),
)


class TopToolbar(QtWidgets.QToolBar):
    modeChanged = QtCore.pyqtSignal(int)
    toolChanged = QtCore.pyqtSignal(str)
    presetChanged = QtCore.pyqtSignal(int)
    actionTriggered = QtCore.pyqtSignal(str)

    COMPACT_BREAKPOINT = 2000
    ICONIC_BREAKPOINT = 1050
    SECONDARY_BREAKPOINT = 1480

    def __init__(self, parent=None):
        super().__init__("Основные действия", parent)
        self.setMovable(False)
        self.setFloatable(False)
        self.setObjectName("mainToolbar")
        self.setIconSize(QtCore.QSize(20, 20))
        self.is_dark_theme = False
        self._secondary_buttons = []
        self._primary_buttons = {}
        self._action_icons = {}
        self._built = False

    def build_toolbar(self):
        self.clear()
        self._surface = QtWidgets.QWidget(self)
        self._surface.setObjectName("toolbarSurface")
        self._layout = QtWidgets.QHBoxLayout(self._surface)
        self._layout.setContentsMargins(12, 6, 12, 6)
        self._layout.setSpacing(4)
        self.addWidget(self._surface)

        self.tool_group = QtGui.QActionGroup(self)
        self.tool_group.setExclusive(True)
        self.tool_actions = {}
        self.mode_group = QtGui.QActionGroup(self)
        self.mode_group.setExclusive(True)
        self.mode_actions = []
        self._secondary_buttons = []
        self._primary_buttons = {}
        self._action_icons = {}

        for action_id in PERMANENT_PRIMARY_ORDER:
            spec = PRIMARY_SPECS[action_id]
            button = self._make_primary_button(spec)
            self._primary_buttons[action_id] = button
            self._layout.addWidget(button)

        self._layout.addWidget(self._separator())

        for spec in SECONDARY_SPECS:
            action = self._make_action(spec)
            button = self._make_secondary_button(action, spec)
            self._secondary_buttons.append((spec, action, button))
            self._layout.addWidget(button)

        # Layout choices remain available in the overflow and appear as compact
        # buttons only when the toolbar has generous desktop width.
        for index, (icon, label) in enumerate((
            ("square", "Один снимок"),
            ("columns-2", "Два снимка"),
            ("grid-2x2", "Четыре снимка"),
        )):
            action = QtGui.QAction(label, self)
            action.setCheckable(True)
            action.setData(index)
            action.setToolTip(label)
            action.triggered.connect(lambda _checked=False, idx=index: self._on_mode_clicked(idx))
            self.mode_group.addAction(action)
            self.mode_actions.append(action)
            self._surface.addAction(action)
            spec = _ActionSpec(f"layout_{index}", icon, label, label)
            button = self._make_secondary_button(action, spec)
            self._secondary_buttons.append((spec, action, button))
            self._layout.addWidget(button)
        self.mode_actions[0].setChecked(True)

        self._layout.addStretch(1)
        self.more_button = QtWidgets.QToolButton(self._surface)
        self.more_button.setObjectName("moreButton")
        self.more_button.setProperty("buttonStyle", "secondary")
        self.more_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.more_button.setText("Ещё")
        self.more_button.setToolTip("Дополнительные действия")
        self.more_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.more_button.clicked.connect(self._show_more_menu)
        self._layout.addWidget(self.more_button)

        # Hidden compatibility control used by the established preset handler.
        self.preset_combo = QtWidgets.QComboBox(self)
        self.preset_combo.addItems(DICOM_PRESETS.keys())
        self.preset_combo.currentIndexChanged.connect(self.presetChanged.emit)
        self.preset_combo.hide()

        self._none_action = QtGui.QAction("Курсор", self)
        self._none_action.setCheckable(True)
        self._none_action.setData(ToolManager.TOOL_NONE)
        self.tool_group.addAction(self._none_action)
        self.tool_actions[ToolManager.TOOL_NONE] = self._none_action
        self._none_action.setChecked(True)

        self._built = True
        self.update_toolbar_icons()
        QtCore.QTimer.singleShot(0, self._update_responsive_state)

    def _make_primary_button(self, spec):
        initial_text = {
            "info": "Инфо",
            "open_folder": "Открыть",
            "adjustments": "",
            "zoom": "",
            "focus": "",
        }[spec.action_id]
        button = QtWidgets.QPushButton(initial_text, self._surface)
        button.setObjectName(f"primaryAction_{spec.action_id}")
        button.setProperty("buttonStyle", "secondary" if spec.action_id == "info" else "ghost")
        if spec.action_id == "open_folder":
            button.setProperty("buttonStyle", "primary")
        button.setMinimumHeight(44)
        initially_icon_only = spec.action_id in ("adjustments", "zoom", "focus")
        button.setProperty("iconOnly", initially_icon_only)
        if initially_icon_only:
            button.setMaximumWidth(GEOMETRY["hit_target"])
        button.setToolTip(spec.tooltip)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        if spec.action_id == "zoom":
            button.clicked.connect(self._show_zoom_menu)
        else:
            button.clicked.connect(lambda _checked=False, action_id=spec.action_id: self.actionTriggered.emit(action_id))
        if spec.shortcut and spec.action_id != "focus":
            shortcut = QtGui.QShortcut(QtGui.QKeySequence(spec.shortcut), self.window())
            shortcut.activated.connect(button.click)
            button._shortcut = shortcut
        return button

    def _make_action(self, spec):
        action = QtGui.QAction(spec.text, self)
        action.setToolTip(spec.tooltip)
        if spec.shortcut:
            action.setShortcut(QtGui.QKeySequence(spec.shortcut))
        if spec.tool_id:
            action.setCheckable(True)
            action.setData(spec.tool_id)
            action.triggered.connect(
                lambda checked=False, tool_id=spec.tool_id: self.toolChanged.emit(tool_id) if checked else None
            )
            self.tool_group.addAction(action)
            self.tool_actions[spec.tool_id] = action
        else:
            action.triggered.connect(
                lambda _checked=False, action_id=spec.action_id: self.actionTriggered.emit(action_id)
            )
        self._surface.addAction(action)
        self._action_icons[action] = spec.icon
        return action

    def _make_secondary_button(self, action, spec):
        button = QtWidgets.QToolButton(self._surface)
        button.setObjectName(f"secondaryAction_{spec.action_id}")
        button.setProperty("buttonStyle", "ghost")
        button.setProperty("iconOnly", True)
        button.setFixedSize(GEOMETRY["hit_target"], GEOMETRY["hit_target"])
        button.setToolTip(spec.tooltip)
        button.setCheckable(action.isCheckable())
        button.clicked.connect(action.trigger)
        action.toggled.connect(button.setChecked)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        # Start overflow-only so the layout never inflates a laptop window
        # before its first responsive width calculation.
        button.hide()
        return button

    def _separator(self):
        separator = QtWidgets.QFrame(self._surface)
        separator.setObjectName("toolbarSeparator")
        separator.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        return separator

    def _on_mode_clicked(self, index):
        if 0 <= index < len(self.mode_actions):
            self.mode_actions[index].setChecked(True)
        self.modeChanged.emit(index)

    def _show_zoom_menu(self):
        menu = RoundMenu(parent=self)
        for icon, text, action_id, shortcut in (
            ("zoom-in", "Увеличить", "zoom_in", "Ctrl++"),
            ("zoom-out", "Уменьшить", "zoom_out", "Ctrl+-"),
            ("maximize", "Вписать в окно", "reset_view", "Ctrl+0"),
        ):
            action = QtGui.QAction(make_icon(icon, self._icon_color(), 18), text, menu)
            action.setShortcut(QtGui.QKeySequence(shortcut))
            action.triggered.connect(lambda _checked=False, value=action_id: self.actionTriggered.emit(value))
            menu.addAction(action)
        pos = self._primary_buttons["zoom"].mapToGlobal(QtCore.QPoint(0, self._primary_buttons["zoom"].height() + 4))
        menu.exec(pos)

    def _show_more_menu(self):
        menu = RoundMenu("Дополнительные действия", self)
        hidden_specs = [(spec, action) for spec, action, button in self._secondary_buttons if not button.isVisible()]
        for spec, action in hidden_specs:
            menu.addAction(action)
        if hidden_specs:
            menu.addSeparator()
        for icon, text, action_id in (
            ("file-plus-2", "Открыть отдельный файл", "open_file"),
            ("circle-help", "Как пользоваться", "help"),
        ):
            action = QtGui.QAction(make_icon(icon, self._icon_color(), 18), text, menu)
            action.triggered.connect(lambda _checked=False, value=action_id: self.actionTriggered.emit(value))
            menu.addAction(action)
        menu.exec(self.more_button.mapToGlobal(QtCore.QPoint(0, self.more_button.height() + 4)))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_responsive_state()

    def _update_responsive_state(self):
        if not self._built:
            return
        compact = self.width() <= self.COMPACT_BREAKPOINT
        iconic = self.width() <= self.ICONIC_BREAKPOINT
        compact_text = {
            "info": "Инфо",
            "open_folder": "Открыть",
            "adjustments": "Яркость / Контраст",
            "zoom": "Масштаб",
            # The shorter human-readable label leaves enough room for every
            # level-two icon on a 1920 px desktop, including the two new
            # cleanup actions. The full explanation remains in the tooltip.
            "focus": "Экран",
        }
        for action_id in PERMANENT_PRIMARY_ORDER:
            button = self._primary_buttons[action_id]
            icon_only = iconic and action_id in ("adjustments", "zoom", "focus")
            button.setText("" if icon_only else compact_text[action_id] if compact else PRIMARY_SPECS[action_id].text)
            button.setProperty("iconOnly", icon_only)
            button.setMaximumWidth(GEOMETRY["hit_target"] if icon_only else 16777215)
            button.style().unpolish(button)
            button.style().polish(button)

        # At common laptop widths every level-two action is deliberately in
        # “Ещё”. On large screens actions return in order while they fit.
        primary_width = sum(button.sizeHint().width() for button in self._primary_buttons.values())
        more_width = self.more_button.sizeHint().width()
        secondary_costs = [
            max(GEOMETRY["hit_target"], min(button.sizeHint().width(), button.maximumWidth())) + self._layout.spacing()
            for _spec, _action, button in self._secondary_buttons
        ]
        fits_all = self.width() >= self.SECONDARY_BREAKPOINT and sum(secondary_costs) <= max(0, self.width() - primary_width - 72)
        budget = max(0, self.width() - primary_width - more_width - 80)
        show_secondary = self.width() >= self.SECONDARY_BREAKPOINT
        used = 0
        for (_spec, _action, button), cost in zip(self._secondary_buttons, secondary_costs):
            visible = fits_all or (show_secondary and used + cost <= budget)
            button.setVisible(visible)
            if visible:
                used += cost
        self.more_button.setVisible(any(not button.isVisible() for _s, _a, button in self._secondary_buttons))

    def set_current_mode(self, index):
        if 0 <= index < len(self.mode_actions):
            self.mode_actions[index].setChecked(True)

    @property
    def mode_combo(self):
        class _ModeProxy:
            def __init__(self, toolbar):
                self._toolbar = toolbar

            def setCurrentIndex(self, index):
                self._toolbar.set_current_mode(index)

            def currentIndex(self):
                for index, action in enumerate(self._toolbar.mode_actions):
                    if action.isChecked():
                        return index
                return 0

        return _ModeProxy(self)

    def _icon_color(self):
        return theme_tokens(self.is_dark_theme)["text_primary"]

    def update_toolbar_icons(self):
        if not self._built:
            return
        color = self._icon_color()
        for action_id, button in self._primary_buttons.items():
            icon_name = PRIMARY_SPECS[action_id].icon
            button.setIcon(make_icon(icon_name, "#FFFFFF" if action_id == "open_folder" else color, 20))
            button.setIconSize(QtCore.QSize(20, 20))
        for spec, action, button in self._secondary_buttons:
            icon_name = spec.icon
            if spec.action_id == "toggle_theme":
                icon_name = "sun" if self.is_dark_theme else "moon"
                action.setText("Светлая тема" if self.is_dark_theme else "Тёмная тема")
            icon = make_icon(icon_name, color, 20)
            action.setIcon(icon)
            button.setIcon(icon)
            button.setIconSize(QtCore.QSize(20, 20))
        self.more_button.setIcon(make_icon("ellipsis", color, 20))
        self.more_button.setIconSize(QtCore.QSize(20, 20))

    def set_tool_for_visible_views(self, tool_name):
        if tool_name not in self.tool_actions:
            tool_name = ToolManager.TOOL_NONE
        action = self.tool_actions.get(tool_name)
        if action and not action.isChecked():
            action.setChecked(True)
