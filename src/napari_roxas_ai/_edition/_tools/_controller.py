"""
LayerTools: binds a ToolBar to one napari layer, in sync both ways with the
layer's mode (napari's tools are only selected, ``layer.mode = name``).
CustomTool: the base of our own tools. UNDO_ACTION: the editor's undo button.
"""

from collections.abc import Callable, Sequence
from contextlib import contextmanager
from pathlib import Path

from qtpy.QtCore import QTimer

from ._companion import owner_of
from ._toolbar import ToolBar, ToolSpec

UNDO = "undo"

# Undo of the edit session: the editor's own undo (``EditToolsPanel.set_undo``)
UNDO_ACTION = ToolSpec(
    UNDO,
    str(Path(__file__).parent / "icons" / "undo.svg"),
    "Undo last change (Ctrl+Z)",
    checkable=False,
)


class CustomTool:
    """
    A tool of ours, shown next to napari's tools.

    ``activate`` is called when it is picked, with the attached layer; it
    usually sets a napari mode (through ``tools.set_mode`` so the toolbar keeps
    it checked) and adds mouse callbacks. ``deactivate`` undoes it, when
    another tool is picked, the mode is changed elsewhere (e.g. napari's
    layer controls) or the layer is detached.
    """

    spec: ToolSpec

    def activate(self, tools: "LayerTools", layer) -> None:
        raise NotImplementedError

    def deactivate(self, tools: "LayerTools", layer) -> None:
        raise NotImplementedError


class LayerTools:
    """
    The tools of ``toolbar`` acting on the attached layer.

    Enforcing a 2-way sync with naparis editing tools.
    """

    def __init__(
        self,
        viewer,
        toolbar: ToolBar,
        *,
        custom_tools: Sequence[CustomTool] = (),
        actions: dict[str, Callable] | None = None,
        action_states: Callable[[object], dict[str, bool]] | None = None,
    ):
        self._viewer = viewer
        self._toolbar = toolbar
        self._custom = {tool.spec.name: tool for tool in custom_tools}
        self._actions = actions or {}
        self._action_states = action_states
        self._layer = None
        self._active_custom: CustomTool | None = None
        # Mode changes made here (not by the user)
        self._setting_mode = False

        toolbar.tool_changed.connect(
            self.select_tool
        )  # button selection -> napari sync
        toolbar.action_triggered.connect(self._on_action)

    # -- Attaching --

    @property
    def layer(self):
        return self._layer

    @property
    def toolbar(self) -> ToolBar:
        return self._toolbar

    @property
    def active_custom_tool(self) -> CustomTool | None:
        return self._active_custom

    def attach(self, layer) -> None:
        self.detach()
        self._layer = layer
        layer.events.mode.connect(
            self._on_layer_mode
        )  # napari -> button selection sync
        if hasattr(layer.events, "highlight"):
            layer.events.highlight.connect(self.update_actions)
        self._viewer.layers.selection.events.active.connect(
            self._on_active_layer
        )
        self._viewer.layers.events.removed.connect(self._on_layer_removed)
        self._sync_checked()
        self.update_actions()

    def detach(self) -> None:
        layer, self._layer = self._layer, None
        if layer is None:
            return
        self._deactivate_custom(layer)
        layer.events.mode.disconnect(self._on_layer_mode)
        if hasattr(layer.events, "highlight"):
            layer.events.highlight.disconnect(self.update_actions)
        self._viewer.layers.selection.events.active.disconnect(
            self._on_active_layer
        )
        self._viewer.layers.events.removed.disconnect(self._on_layer_removed)
        self._toolbar.set_checked(None)

    # -- Tools --

    def select_tool(self, name: str | None) -> None:
        """Use the tool ``name`` (None: back to pan/zoom)."""
        layer = self._layer
        if layer is None:
            self._toolbar.set_checked(None)
            return
        if self._viewer.layers.selection.active is not layer:
            self._viewer.layers.selection.active = layer

        tool = self._custom.get(name)
        if tool is not self._active_custom:
            self._deactivate_custom(layer)
        if tool is not None:
            if self._active_custom is None:
                self._active_custom = tool
                tool.activate(self, layer)
        else:
            self.set_mode(layer, name or "pan_zoom")
        self._sync_checked()

    def set_mode(self, layer, mode: str) -> None:
        """Set a napari mode without it counting as a change of tool."""
        with self._own_mode_change():
            layer.mode = mode

    @contextmanager
    def _own_mode_change(self):
        self._setting_mode = True
        try:
            yield
        finally:
            self._setting_mode = False

    def _deactivate_custom(self, layer) -> None:
        tool, self._active_custom = self._active_custom, None
        if tool is not None:
            tool.deactivate(self, layer)

    def _sync_checked(self) -> None:
        layer = self._layer
        if layer is None or self._viewer.layers.selection.active is not layer:
            self._toolbar.set_checked(None)
        elif self._active_custom is not None:
            self._toolbar.set_checked(self._active_custom.spec.name)
        else:
            self._toolbar.set_checked(str(layer.mode))

    def _on_layer_mode(self, _event=None) -> None:
        if self._setting_mode or self._layer is None:
            return
        # A mode chosen elsewhere (e.g. napari's layer controls)
        self._deactivate_custom(self._layer)
        self._sync_checked()

    def _on_active_layer(self, _event=None) -> None:
        # Checked once the active layer settled: layers added by tools (e.g.
        # an outline) briefly become active
        QTimer.singleShot(0, self._check_active_layer)

    def _check_active_layer(self) -> None:
        layer = self._layer
        if layer is None:
            return
        active = self._viewer.layers.selection.active
        # A layer of the edited layer (selecting it selects the edited layer)
        if active is not layer and owner_of(active) is not layer:
            self._deactivate_custom(layer)
        self._sync_checked()

    def _on_layer_removed(self, event) -> None:
        if event.value is self._layer:
            self.detach()

    # -- Actions --

    def _on_action(self, name: str) -> None:
        handler = self._actions.get(name)
        if self._layer is not None and handler is not None:
            handler(self._layer)
        self.update_actions()

    def update_actions(self, _event=None) -> None:
        if self._action_states is None:
            return
        layer = self._layer
        states = self._action_states(layer) if layer is not None else {}
        for name in self._actions:
            self._toolbar.set_enabled(name, bool(states.get(name, False)))
