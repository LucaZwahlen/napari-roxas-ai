from qtpy.QtCore import QTimer

# Companion layer -> its owner (until released)
_OWNERS: dict = {}


def owner_of(layer):
    """The layer ``layer`` belongs to (None: it belongs to no layer)."""
    return _OWNERS.get(layer) if layer is not None else None


class CompanionLayer:
    """
    Adds ``layer`` to the viewer, tied to ``owner`` until ``release``:

    - it is named after its owner ("[<owner>] - overlay"), whatever renames;
    - it stays visible and locked against deletion; removed anyway, it is
      added back;
    - it stays right above its owner;
    - it is never selected: selecting it selects the owner.

    Adding it does not change the active layer.
    """

    def __init__(self, viewer, layer, owner):
        self._viewer = viewer
        self._layer = layer
        self._owner = owner
        self._released = False
        self._naming = False
        _OWNERS[layer] = owner
        layer.name = self._name()
        layer.locked = True
        self._insert()

        layer.events.name.connect(self._on_name)
        owner.events.name.connect(self._on_name)
        layer.events.visible.connect(self._on_visible)
        layer.events.locked.connect(self._on_locked)
        viewer.layers.events.removed.connect(self._on_removed)
        viewer.layers.events.inserted.connect(self._on_reordered)
        viewer.layers.events.moved.connect(self._on_reordered)
        viewer.layers.selection.events.changed.connect(self._on_selection)

    def release(self) -> None:
        """Untie the layer and remove it from the viewer."""
        if self._released:
            return
        self._released = True
        layer, layers = self._layer, self._viewer.layers
        layer.events.name.disconnect(self._on_name)
        self._owner.events.name.disconnect(self._on_name)
        layer.events.visible.disconnect(self._on_visible)
        layer.events.locked.disconnect(self._on_locked)
        layers.events.removed.disconnect(self._on_removed)
        layers.events.inserted.disconnect(self._on_reordered)
        layers.events.moved.disconnect(self._on_reordered)
        layers.selection.events.changed.disconnect(self._on_selection)
        _OWNERS.pop(layer, None)
        if layer in layers:
            layer.locked = False
            layers.remove(layer)

    # -- Internals --

    def _alive(self) -> bool:
        return not self._released and self._owner in self._viewer.layers

    def _insert(self) -> None:
        """Insert the layer above its owner, keeping the active layer."""
        layers = self._viewer.layers
        active = layers.selection.active
        index = layers.index(self._owner) + 1 if self._owner in layers else 0
        layers.insert(index, self._layer)
        if active is not None and active in layers:
            layers.selection.active = active

    def _name(self) -> str:
        return f"[{self._owner.name}] - overlay"

    def _on_name(self, _event=None) -> None:
        # Guarded: napari may make the name unique, which renames it again
        if self._naming or self._layer.name == self._name():
            return
        self._naming = True
        try:
            self._layer.name = self._name()
        finally:
            self._naming = False

    def _on_visible(self, _event=None) -> None:
        if not self._layer.visible:
            self._layer.visible = True

    def _on_locked(self, _event=None) -> None:
        if not self._layer.locked:
            self._layer.locked = True

    def _on_removed(self, event) -> None:
        if event.value is self._layer:
            # Deferred: napari is still removing it
            QTimer.singleShot(0, self._restore)

    def _restore(self) -> None:
        if self._alive() and self._layer not in self._viewer.layers:
            self._insert()

    def _on_reordered(self, _event=None) -> None:
        # Deferred: the layer list is still changing
        QTimer.singleShot(0, self._keep_above_owner)

    def _keep_above_owner(self) -> None:
        layers = self._viewer.layers
        if not self._alive() or self._layer not in layers:
            return
        index, owner_index = layers.index(self._layer), layers.index(
            self._owner
        )
        if index != owner_index + 1:
            layers.move(index, owner_index + 1)

    def _on_selection(self, _event=None) -> None:
        if self._layer in self._viewer.layers.selection:
            # Deferred: the layer list view is still changing the selection
            QTimer.singleShot(0, self._select_owner)

    def _select_owner(self) -> None:
        selection = self._viewer.layers.selection
        if self._released or self._layer not in selection:
            return
        # The owner in its place (added first: the selection never empties)
        if self._alive():
            selection.add(self._owner)
        selection.discard(self._layer)
