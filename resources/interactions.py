"""Shared micro-interactions for QWidget controls."""

from PyQt6 import QtCore, QtWidgets
from qfluentwidgets import ToolTipFilter, ToolTipPosition

from resources.design_tokens import GEOMETRY, qcolor, theme_tokens


class _ButtonHoverAnimator(QtCore.QObject):
    def __init__(self, button, dark=False):
        super().__init__(button)
        self.button = button
        self.dark = dark
        self.progress = 0.0
        self.effect = QtWidgets.QGraphicsDropShadowEffect(button)
        self.effect.setOffset(0, 0)
        self.effect.setBlurRadius(0)
        self.effect.setColor(qcolor(theme_tokens(dark)["shadow_color"]))
        button.setGraphicsEffect(self.effect)
        self.animation = QtCore.QVariantAnimation(self)
        self.animation.setDuration(GEOMETRY["transition_fast"])
        self.animation.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)
        self.animation.valueChanged.connect(self._apply)
        button.installEventFilter(self)

    def eventFilter(self, watched, event):
        if event.type() == QtCore.QEvent.Type.Enter and watched.isEnabled():
            self._animate_to(1.0)
        elif event.type() == QtCore.QEvent.Type.Leave:
            self._animate_to(0.0)
        elif event.type() == QtCore.QEvent.Type.MouseButtonPress and watched.isEnabled():
            self._animate_to(0.28)
        elif event.type() == QtCore.QEvent.Type.MouseButtonRelease and watched.isEnabled():
            self._animate_to(1.0 if watched.underMouse() else 0.0)
        return False

    def _animate_to(self, target):
        self.animation.stop()
        self.animation.setStartValue(self.progress)
        self.animation.setEndValue(float(target))
        self.animation.start()

    def _apply(self, value):
        self.progress = float(value)
        self.effect.setBlurRadius(12.0 * self.progress)
        self.effect.setOffset(0, 2.0 * self.progress)
        color = qcolor(theme_tokens(self.dark)["shadow_color"])
        color.setAlpha(round(color.alpha() * self.progress))
        self.effect.setColor(color)


def install_button_interactions(root, dark=False, animate=True):
    """Install 150 ms hover depth and 500 ms Fluent tooltips once."""
    for button in root.findChildren(QtWidgets.QAbstractButton):
        if animate and not button.property("premiumInteractionInstalled"):
            button.setProperty("premiumInteractionInstalled", True)
            button._hover_animator = _ButtonHoverAnimator(button, dark)
        if button.toolTip() and not button.property("premiumTooltipInstalled"):
            button.setProperty("premiumTooltipInstalled", True)
            tooltip_filter = ToolTipFilter(button, showDelay=500, position=ToolTipPosition.TOP)
            button.installEventFilter(tooltip_filter)
            button._premium_tooltip_filter = tooltip_filter
