from collections.abc import Sequence
from dataclasses import dataclass
from functools import partial

from magicgui.widgets import Container
from napari.resources import get_colorized_svg, get_icon_path
from napari.utils.theme import darken, get_theme
from psygnal import Signal
from qtpy.QtCore import QByteArray, QSize, Qt
from qtpy.QtGui import QIcon, QPainter, QPixmap
from qtpy.QtSvg import QSvgRenderer
from qtpy.QtWidgets import QHBoxLayout, QToolButton, QVBoxLayout, QWidget

BUTTON_SIZE = 28
ICON_SIZE = 24
SEPARATOR_SPACING = 10


@dataclass(frozen=True)
class ToolSpec:
    """
    A button of the toolbar.

    ``icon`` is a napari icon name or the path to an svg file. A checkable
    button is a tool (only one is checked at a time); otherwise an action.
    """

    name: str
    icon: str
    tooltip: str
    checkable: bool = True


# None in a row adds a separator
ToolRows = Sequence[Sequence[ToolSpec | None]]


def _render_icon(source: str, color: str) -> QIcon:
    path = source if source.endswith(".svg") else get_icon_path(source)
    renderer = QSvgRenderer(
        QByteArray(get_colorized_svg(path, color).encode())
    )
    icon = QIcon()
    # Rendered at twice the size too, for high-dpi screens
    for size in (ICON_SIZE, 2 * ICON_SIZE):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        icon.addPixmap(pixmap)
    return icon


class ToolBar(Container):
    """
    Rows of tool and action buttons.

    At most one tool is checked; clicking the checked tool unchecks it.
    Clicks emit ``tool_changed`` and ``action_triggered``. ``set_checked`` changes the checked
    tool without emitting.
    """

    tool_changed = Signal(object)
    action_triggered = Signal(str)
    # The checked tool changed, by a click or by ``set_checked``
    checked_changed = Signal(object)

    def __init__(self, viewer, rows: ToolRows, **kwargs):
        kwargs.setdefault("labels", False)
        super().__init__(**kwargs)
        self.margins = (0, 0, 0, 0)
        self._viewer = viewer
        self._specs: dict[str, ToolSpec] = {}
        self._buttons: dict[str, QToolButton] = {}
        self._checked: str | None = None

        self._panel = QWidget()
        panel_layout = QVBoxLayout(self._panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(4)
        for row in rows:
            row_layout = QHBoxLayout()
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(4)
            for spec in row:
                if spec is None:
                    row_layout.addSpacing(SEPARATOR_SPACING)
                else:
                    row_layout.addWidget(self._make_button(spec))
            row_layout.addStretch(1)
            panel_layout.addLayout(row_layout)
        self.native.layout().addWidget(self._panel)

        viewer.events.theme.connect(self._apply_theme)
        self._apply_theme()

    def _make_button(self, spec: ToolSpec) -> QToolButton:
        button = QToolButton()
        button.setObjectName("roxasToolButton")
        button.setFixedSize(BUTTON_SIZE, BUTTON_SIZE)
        button.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        button.setToolTip(spec.tooltip)
        button.setCheckable(spec.checkable)
        if spec.checkable:
            button.clicked.connect(partial(self._on_tool_clicked, spec.name))
        else:
            button.clicked.connect(partial(self._on_action_clicked, spec.name))
        self._specs[spec.name] = spec
        self._buttons[spec.name] = button
        return button

    # -- State --

    @property
    def checked(self) -> str | None:
        return self._checked

    def set_checked(self, name: str | None) -> None:
        """Check the tool ``name`` (None, or not a tool: none) silently."""
        spec = self._specs.get(name)
        previous = self._checked
        self._checked = name if spec is not None and spec.checkable else None
        for tool, button in self._buttons.items():
            if button.isCheckable():
                button.setChecked(tool == self._checked)
        if self._checked != previous:
            self.checked_changed.emit(self._checked)

    def set_enabled(self, name: str, enabled: bool) -> None:
        if name in self._buttons:
            self._buttons[name].setEnabled(enabled)

    def _on_tool_clicked(self, name: str, checked: bool) -> None:
        self.set_checked(name if checked else None)
        self.tool_changed.emit(self._checked)

    def _on_action_clicked(self, name: str, _checked: bool = False) -> None:
        self.action_triggered.emit(name)

    # -- Styling --

    def _apply_theme(self, _event=None) -> None:
        try:
            theme = get_theme(self._viewer.theme)
            icon_color = theme.icon.as_hex()
            for name, button in self._buttons.items():
                button.setIcon(
                    _render_icon(self._specs[name].icon, icon_color)
                )
            # As napari's mode buttons
            self._panel.setStyleSheet(
                f"""
                QToolButton#roxasToolButton {{
                    border: none;
                    border-radius: 3px;
                    padding: 0px;
                    background-color: {theme.primary.as_hex()};
                }}
                QToolButton#roxasToolButton:hover {{
                    background-color: {theme.highlight.as_hex()};
                }}
                QToolButton#roxasToolButton:checked {{
                    background-color: {theme.current.as_hex()};
                }}
                QToolButton#roxasToolButton:disabled {{
                    background-color: {darken(theme.foreground, 20)};
                }}
                """
            )
        except RuntimeError:
            # The Qt widgets were deleted (widget closed)
            self._viewer.events.theme.disconnect(self._apply_theme)
