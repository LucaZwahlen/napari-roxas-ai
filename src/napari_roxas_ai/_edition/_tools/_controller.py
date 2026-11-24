from collections.abc import Callable, Sequence
from contextlib import contextmanager
from pathlib import Path

from qtpy.QtCore import QTimer

from ._toolbar import ToolBar, ToolRows, ToolSpec

DELETE = "delete"
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


# napari's Shapes modes offered for polygon editing (no layer transform, ellipses, lines, paths)
SHAPES_TOOLS = {
    "pan_zoom": ToolSpec("pan_zoom", "pan_arrows", "Pan/zoom"),
    "select": ToolSpec("select", "select", "Select shapes"),
    "direct": ToolSpec("direct", "direct", "Select vertices"),
    "vertex_insert": ToolSpec(
        "vertex_insert", "vertex_insert", "Insert vertex"
    ),
    "vertex_remove": ToolSpec(
        "vertex_remove", "vertex_remove", "Remove vertex"
    ),
    "add_rectangle": ToolSpec("add_rectangle", "rectangle", "Add rectangles"),
    "add_polygon": ToolSpec("add_polygon", "polygon", "Add polygons"),
    "add_polygon_lasso": ToolSpec(
        "add_polygon_lasso", "polygon_lasso", "Add polygons with a lasso"
    ),
}

# napari's Labels modes offered (no layer transform)
LABELS_TOOLS = {
    "pan_zoom": ToolSpec("pan_zoom", "pan_arrows", "Pan/zoom"),
    "pick": ToolSpec("pick", "picker", "Pick a label"),
    "paint": ToolSpec("paint", "paint", "Paint"),
    "polygon": ToolSpec("polygon", "polygon", "Draw a polygon label"),
    "fill": ToolSpec("fill", "fill", "Fill"),
    "erase": ToolSpec("erase", "erase", "Erase"),
}

SHAPES_ACTIONS = {
    DELETE: ToolSpec(
        DELETE, "delete_shape", "Delete selected (Delete)", checkable=False
    ),
}


def shapes_rows(custom: Sequence[CustomTool] = ()) -> ToolRows:
    """napari's Shapes tools; custom tools follow the selection tools."""
    t = SHAPES_TOOLS
    return [
        [
            t["pan_zoom"],
            t["select"],
            *(tool.spec for tool in custom),
            t["direct"],
            t["vertex_insert"],
            t["vertex_remove"],
            None,
            SHAPES_ACTIONS[DELETE],
            UNDO_ACTION,
        ],
        [
            t["add_rectangle"],
            t["add_polygon"],
            t["add_polygon_lasso"],
        ],
    ]


def labels_rows(custom: Sequence[CustomTool] = ()) -> ToolRows:
    """napari's Labels tools, then the custom tools."""
    t = LABELS_TOOLS
    row = [
        t["pan_zoom"],
        t["pick"],
        t["paint"],
        t["polygon"],
        t["fill"],
        t["erase"],
        None,
        UNDO_ACTION,
    ]
    if custom:
        row += [None, *(tool.spec for tool in custom)]
    return [row]


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
        if self._viewer.layers.selection.active is not layer:
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


def shapes_actions() -> dict[str, Callable]:
    """Handlers of the Shapes action buttons."""
    return {DELETE: lambda layer: layer.remove_selected()}


def shapes_action_states(layer) -> dict[str, bool]:
    selected = len(layer.selected_data) > 0
    return {DELETE: selected}
