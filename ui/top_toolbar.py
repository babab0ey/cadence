import sys
import os
from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtCore import Qt
from tools.tool_manager import ToolManager
from core.utils import DICOM_PRESETS

# Import the Claude SVG icons
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from resources.icons import make_icon


# Theme-aware icon colors
LIGHT_ICON_COLOR = "#3D3D3A"
LIGHT_ICON_HOVER = "#141413"
DARK_ICON_COLOR = "#C2C0B6"
DARK_ICON_HOVER = "#FAF9F5"
ACCENT_COLOR = "#D97757"


class TopToolbar(QtWidgets.QToolBar):
    modeChanged = QtCore.pyqtSignal(int)
    toolChanged = QtCore.pyqtSignal(str)
    presetChanged = QtCore.pyqtSignal(int)
    actionTriggered = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__("Инструменты", parent)
        self.setMovable(False)
        self.setObjectName("mainToolbar")
        self.setIconSize(QtCore.QSize(18, 18))
        self.toolbar_actions_config = []  # [(action, icon_name)]
        self.is_dark_theme = False

    def build_toolbar(self):
        self.clear()
        self.toolbar_actions_config = []
        self.tool_actions = {}

        # ── File actions ──
        self._add_button("file-open", "Открыть", "open_file", "Ctrl+O", tooltip="Открыть файл (Ctrl+O)")
        self._add_button("folder-open", "Папка", "open_folder", "Ctrl+Shift+O", tooltip="Открыть папку (Ctrl+Shift+O)")
        self._add_button("save", "Экспорт", "export", "Ctrl+S", tooltip="Сохранить как изображение (Ctrl+S)")
        self._add_button("info", "Инфо", "info", "Ctrl+I", tooltip="DICOM информация (Ctrl+I)")

        self.addSeparator()

        # ── Mode selector with icons ──
        mode_label = QtWidgets.QLabel(" Режим ")
        mode_label.setObjectName("mutedLabel")
        self.addWidget(mode_label)

        self.mode_group = QtGui.QActionGroup(self)
        self.mode_group.setExclusive(True)

        self.mode_actions = []
        for i, (icon_name, label) in enumerate([
            ("layout-single", "1×1"),
            ("layout-double", "1×2"),
            ("layout-quad", "2×2"),
        ]):
            act = QtGui.QAction(label, self)
            act.setCheckable(True)
            act.setToolTip(f"Режим: {label}")
            act.triggered.connect(lambda checked, idx=i: self._on_mode_clicked(idx))
            self.mode_group.addAction(act)
            self.addAction(act)
            self.toolbar_actions_config.append((act, icon_name))
            self.mode_actions.append(act)
        self.mode_actions[0].setChecked(True)

        self.addSeparator()

        # ── Tool group (exclusive) ──
        self.tool_group = QtGui.QActionGroup(self)
        self.tool_group.setExclusive(True)

        tools_config = [
            (ToolManager.TOOL_NONE, "cursor", "Курсор", ""),
            (ToolManager.TOOL_RULER, "ruler", "Рулетка", "Alt+R"),
            (ToolManager.TOOL_ANGLE, "angle", "Угол", "Alt+A"),
            (ToolManager.TOOL_ROI, "rectangle", "Прямоугольник", "Alt+O"),
            (ToolManager.TOOL_ROI_ELLIPSE, "ellipse", "Эллипс", ""),
            (ToolManager.TOOL_POLYGON, "polygon", "Полигон", ""),
            (ToolManager.TOOL_PEN, "pen", "Ручка", "Alt+P"),
            (ToolManager.TOOL_NOTE, "note", "Заметка", "Alt+N"),
        ]
        for tool_id, icon, label, shortcut in tools_config:
            act = QtGui.QAction(label, self)
            act.setCheckable(True)
            act.setData(tool_id)
            act.setToolTip(f"{label}" + (f" ({shortcut})" if shortcut else ""))
            if shortcut:
                act.setShortcut(QtGui.QKeySequence(shortcut))
            act.triggered.connect(lambda checked, tid=tool_id: self.toolChanged.emit(tid) if checked else None)
            self.tool_group.addAction(act)
            self.addAction(act)
            self.toolbar_actions_config.append((act, icon))
            self.tool_actions[tool_id] = act
        self.tool_actions[ToolManager.TOOL_NONE].setChecked(True)

        # eraser
        self._add_button("eraser", "Очистить", "clear_drawings", tooltip="Стереть рисунки")

        self.addSeparator()

        # ── Preset combo (Claude style) ──
        preset_label = QtWidgets.QLabel(" W/L ")
        preset_label.setObjectName("mutedLabel")
        self.addWidget(preset_label)
        self.preset_combo = QtWidgets.QComboBox()
        self.preset_combo.addItems(DICOM_PRESETS.keys())
        self.preset_combo.setMinimumWidth(160)
        self.preset_combo.setToolTip("Пресет окна (Window/Level)")
        self.preset_combo.currentIndexChanged.connect(self.presetChanged.emit)
        self.addWidget(self.preset_combo)

        self.addSeparator()

        # ── Zoom controls ──
        self._add_button("zoom-out", "", "zoom_out", "Ctrl+-", tooltip="Уменьшить (Ctrl+-)")
        self._add_button("zoom-reset", "", "reset_view", "Ctrl+0", tooltip="Сбросить (Ctrl+0)")
        self._add_button("zoom-in", "", "zoom_in", "Ctrl++", tooltip="Увеличить (Ctrl++)")

        self.addSeparator()

        # ── Transform ──
        self._add_button("rotate", "", "rotate", "Ctrl+R", tooltip="Повернуть 90° (Ctrl+R)")
        self._add_button("flip-h", "", "flip_h", "Ctrl+H", tooltip="Отразить горизонтально (Ctrl+H)")
        self._add_button("flip-v", "", "flip_v", "Ctrl+V", tooltip="Отразить вертикально (Ctrl+V)")

        self.addSeparator()

        # ── Adjust + Undo ──
        self._add_button("adjust", "Яркость", "adjustments", tooltip="Яркость и контраст")
        self._add_button("undo", "", "undo", "Ctrl+Z", tooltip="Отменить (Ctrl+Z)")

        # ── Stretch (push right) ──
        spacer = QtWidgets.QWidget()
        spacer.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred)
        spacer.setStyleSheet("background: transparent;")
        self.addWidget(spacer)

        # ── Right side: clear, theme, more ──
        self._add_button("trash", "", "clear_all", tooltip="Очистить все окна")
        self._add_button("focus", "", "focus", tooltip="Полноэкранный режим (F11)")

        # Theme toggle (sun/moon)
        self.theme_action = QtGui.QAction("", self)
        self.theme_action.setToolTip("Сменить тему")
        self.theme_action.triggered.connect(lambda: self.actionTriggered.emit("toggle_theme"))
        self.addAction(self.theme_action)
        self.toolbar_actions_config.append((self.theme_action, "moon"))

        # More menu (⋯)
        tray_btn = QtWidgets.QToolButton()
        tray_btn.setIcon(make_icon("more", LIGHT_ICON_COLOR, 20))
        tray_btn.setToolTip("Дополнительно")
        tray_btn.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)

        tray_menu = QtWidgets.QMenu(self)

        act_settings = QtGui.QAction("Настройки", self)
        act_settings.triggered.connect(lambda: self.actionTriggered.emit("settings"))
        tray_menu.addAction(act_settings)

        act_help = QtGui.QAction("Справка", self)
        act_help.triggered.connect(lambda: self.actionTriggered.emit("help"))
        tray_menu.addAction(act_help)

        tray_menu.addSeparator()

        act_clear_active = QtGui.QAction("Очистить активное окно", self)
        act_clear_active.triggered.connect(lambda: self.actionTriggered.emit("clear_active"))
        tray_menu.addAction(act_clear_active)

        tray_btn.setMenu(tray_menu)
        self._tray_btn = tray_btn
        self.addWidget(tray_btn)

    def _add_button(self, icon_name, text, action_id, shortcut=None, checkable=False, tooltip=None):
        act = QtGui.QAction(text, self)
        if shortcut:
            act.setShortcut(QtGui.QKeySequence(shortcut))
        if checkable:
            act.setCheckable(True)
        if tooltip:
            act.setToolTip(tooltip)
        act.triggered.connect(lambda: self.actionTriggered.emit(action_id))
        self.addAction(act)
        self.toolbar_actions_config.append((act, icon_name))
        return act

    def _on_mode_clicked(self, index):
        self.modeChanged.emit(index)

    def set_current_mode(self, index):
        if 0 <= index < len(self.mode_actions):
            self.mode_actions[index].setChecked(True)

    @property
    def mode_combo(self):
        # Backwards-compat shim — exposes a fake combo-like object
        class _ModeProxy:
            def __init__(self, parent):
                self._p = parent
            def setCurrentIndex(self, i):
                self._p.set_current_mode(i)
            def currentIndex(self):
                for i, a in enumerate(self._p.mode_actions):
                    if a.isChecked():
                        return i
                return 0
        return _ModeProxy(self)

    def update_toolbar_icons(self):
        """Recolor all icons based on current theme."""
        color = DARK_ICON_COLOR if self.is_dark_theme else LIGHT_ICON_COLOR
        for action, icon_name in self.toolbar_actions_config:
            if not icon_name:
                continue
            # Theme action shows opposite-mode icon
            if action is getattr(self, "theme_action", None):
                actual_icon = "sun" if self.is_dark_theme else "moon"
                action.setIcon(make_icon(actual_icon, color, 20))
            else:
                action.setIcon(make_icon(icon_name, color, 20))
        if hasattr(self, "_tray_btn"):
            self._tray_btn.setIcon(make_icon("more", color, 20))

    def set_tool_for_visible_views(self, tool_name):
        if tool_name not in self.tool_actions:
            tool_name = ToolManager.TOOL_NONE
        action = self.tool_actions.get(tool_name)
        if action and not action.isChecked():
            action.setChecked(True)
