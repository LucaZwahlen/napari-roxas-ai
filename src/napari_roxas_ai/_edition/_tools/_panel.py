from collections.abc import Callable, Sequence

from magicgui.widgets import Container

from ._controller import (
    UNDO,
    CustomTool,
    LayerTools,
    labels_rows,
    shapes_action_states,
    shapes_actions,
    shapes_rows,
)
from ._toolbar import ToolBar
from .options import OptionsBox, default_options

PIXEL, VECTOR = "pixel", "vector"
PAGES = (PIXEL, VECTOR)


class EditToolsPanel(Container):
    """
    The tools of an editor's edit session

    - ``pixel``: a raster (Labels) edit session: napari's Labels tools
    - ``vector``: a vector (Shapes) edit session: napari's Shapes tools

    Each page has an options box under its tools (``options.default_options``),
    showing the options of the checked tool. The toolbars take custom tools
    (``set_custom_tools``), which may bring their own options (a ``options`` list
    on the tool).
    """

    def __init__(self, viewer, **kwargs):
        kwargs.setdefault("labels", False)
        super().__init__(**kwargs)
        self.margins = (0, 0, 0, 0)
        self._viewer = viewer
        self._editing: str | None = None
        self._edit_layer = None
        self._custom: dict[str, Sequence[CustomTool]] = {PIXEL: (), VECTOR: ()}
        # The editor's undo, a button of both toolbars
        self._undo_handler: Callable[[], None] | None = None
        self._undo_enabled = False

        self._tools: dict[str, LayerTools] = {}
        self._options: dict[str, OptionsBox] = {}
        self._pages: dict[str, Container] = {
            kind: Container(labels=False) for kind in PAGES
        }
        for kind in PAGES:
            self._build_tools(kind)
        # One page shown at a time (a hidden page takes no space)
        self.extend(list(self._pages.values()))
        self._show_page(PIXEL)

    # -- Editor API --

    def edit_pixels(self, layer) -> None:
        """A raster edit session on the Labels ``layer`` started."""
        self._start(PIXEL, layer)

    def edit_vectors(self, layer) -> None:
        """A vector edit session on the Shapes ``layer`` started."""
        self._start(VECTOR, layer)

    def end_editing(self) -> None:
        for kind in PAGES:
            self._tools[kind].detach()
            self._options[kind].detach()
        self._editing = self._edit_layer = None

    def set_undo(self, handler: Callable[[], None]) -> None:
        """The editor's undo, run by the Undo button of both toolbars."""
        self._undo_handler = handler

    def set_undo_enabled(self, enabled: bool) -> None:
        """Whether there is something to undo (the editor knows)."""
        self._undo_enabled = bool(enabled)
        for tools in self._tools.values():
            tools.update_actions()

    def set_custom_tools(self, kind: str, tools: Sequence[CustomTool]) -> None:
        """Our own tools for the ``pixel`` or ``vector`` toolbar."""
        self._custom[kind] = tuple(tools)
        self._build_tools(kind)

    # -- Internals --

    def _on_undo(self, _layer) -> None:
        if self._undo_handler is not None:
            self._undo_handler()

    def _start(self, kind: str, layer) -> None:
        self.end_editing()
        self._editing, self._edit_layer = kind, layer
        self._attach(kind)
        self._show_page(kind)

    def _show_page(self, kind: str) -> None:
        for page_kind, page in self._pages.items():
            page.visible = page_kind == kind

    def _attach(self, kind: str) -> None:
        self._tools[kind].attach(self._edit_layer)
        self._options[kind].attach(self._edit_layer)
        self._options[kind].set_tool(self._tools[kind].toolbar.checked)

    def _build_tools(self, kind: str) -> None:
        old = self._tools.get(kind)
        if old is not None:
            old.detach()
            self._options[kind].detach()
        page = self._pages[kind]
        page.clear()
        custom = self._custom[kind]
        actions = {UNDO: self._on_undo}
        if kind == PIXEL:
            toolbar = ToolBar(self._viewer, labels_rows(custom))

            def action_states(_layer):
                return {UNDO: self._undo_enabled}

        else:
            toolbar = ToolBar(self._viewer, shapes_rows(custom))
            actions.update(shapes_actions())

            def action_states(layer):
                return {
                    UNDO: self._undo_enabled,
                    **shapes_action_states(layer),
                }

        tools = LayerTools(
            self._viewer,
            toolbar,
            custom_tools=custom,
            actions=actions,
            action_states=action_states,
        )
        options = OptionsBox(
            [
                *default_options(kind),
                *(o for tool in custom for o in getattr(tool, "options", ())),
            ]
        )
        toolbar.checked_changed.connect(options.set_tool)
        page.extend([toolbar, options])
        self._tools[kind] = tools
        self._options[kind] = options
        if self._editing == kind and self._edit_layer is not None:
            self._attach(kind)
