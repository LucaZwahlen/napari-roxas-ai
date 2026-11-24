from collections.abc import Sequence

from magicgui.widgets import CheckBox, Container, Label, Widget

GROUPS = {"tool": "Tool options", "layer": "Layer options"}


class ToolOption:
    """
    A tool option to be implemented.
    Enforcing a 2-way-sync between the tool and naparis options.

    Subclass and define:

    - ``name``, ``label``, ``tools`` (tool names it applies to, None: always);
    - ``group``: ``"tool"`` (a setting of the tools) or ``"layer"``;
    - ``make_widget()``: the magicgui value widget;
    - ``read(layer)`` / ``write(layer, value)``: the layer property;
    - ``layer_event(layer)``: the event emitted when the property changes.
    """

    name: str = ""
    label: str = ""
    tools: frozenset[str] | None = None
    group: str = "tool"

    def make_widget(self) -> Widget:
        raise NotImplementedError

    def read(self, layer):
        raise NotImplementedError

    def write(self, layer, value) -> None:
        raise NotImplementedError

    def layer_event(self, layer):
        raise NotImplementedError

    def applies_to(self, tool: str | None) -> bool:
        return self.tools is None or tool in self.tools


class OptionsBox(Container):
    """The ``options`` of one page, bound to the attached layer."""

    def __init__(self, options: Sequence[ToolOption] = ()):
        super().__init__(labels=False)
        self.margins = (0, 0, 0, 0)
        # Per group: a title and the options under it
        self._titles: dict[str, Label] = {}
        self._groups: dict[str, Container] = {}
        for group, title in GROUPS.items():
            label = Label(value=title)
            label.native.setStyleSheet("font-weight: bold;")
            box = Container(labels=True)
            box.margins = (0, 0, 0, 0)
            self._titles[group], self._groups[group] = label, box
            self.extend([label, box])
        self._layer = None
        self._tool: str | None = None
        self._options: list[ToolOption] = []
        self._widgets: dict[str, Widget] = {}
        self.set_options(options)

    def set_options(self, options: Sequence[ToolOption]) -> None:
        layer = self._layer
        self.detach()
        for box in self._groups.values():
            box.clear()
        self._options = list(options)
        self._widgets = {}
        for option in self._options:
            widget = option.make_widget()
            if isinstance(widget, CheckBox):
                # A checkbox shows its caption itself, not in the label column
                widget.text = option.label
                widget.label = ""
            else:
                widget.label = option.label
            widget.changed.connect(
                lambda value, option=option: self._on_widget(
                    option, value
                )  # button -> napari sync
            )
            self._widgets[option.name] = widget
            self._groups[option.group].append(widget)
        if layer is not None:
            self.attach(layer)
        self._update_visibility()

    def attach(self, layer) -> None:
        self.detach()
        self._layer = layer
        for option in self._options:
            option.layer_event(layer).connect(
                self._on_layer_change
            )  # napari -> button sync
        self._on_layer_change()

    def detach(self) -> None:
        layer, self._layer = self._layer, None
        if layer is None:
            return
        for option in self._options:
            option.layer_event(layer).disconnect(self._on_layer_change)

    def set_tool(self, tool: str | None) -> None:
        self._tool = tool
        self._update_visibility()

    def _update_visibility(self) -> None:
        shown = {group: False for group in GROUPS}
        for option in self._options:
            visible = option.applies_to(self._tool)
            self._widgets[option.name].visible = visible
            shown[option.group] |= visible
        for group, any_shown in shown.items():
            self._titles[group].visible = any_shown
            self._groups[group].visible = any_shown

    def _on_widget(self, option: ToolOption, value) -> None:
        if self._layer is not None:
            option.write(self._layer, value)

    def _on_layer_change(self, _event=None) -> None:
        layer = self._layer
        if layer is None:
            return
        for option in self._options:
            widget = self._widgets[option.name]
            with widget.changed.blocked():
                widget.value = option.read(layer)
