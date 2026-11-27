from magicgui.widgets import ComboBox
from qtpy.QtCore import QEvent, QObject

from ._manager import assets_updated, ensure_assets
from ._registry import Asset

# Where the user can download the assets again, shown in empty dropdowns
DOWNLOAD_MENU_HINT = "Download in File > IO Utilities"


class AssetComboBox(ComboBox):
    """
    Dropdown of the files of an asset (e.g. the cell models).

    The asset is downloaded if missing when the dropdown is first shown (so
    not for widgets that are created hidden). The files are listed again
    after each download, also one started elsewhere (e.g. the File menu).

    Args:
        asset: The asset whose files are listed.
        default: File selected when it is listed.
        suffixes: Only list the files with these suffixes (all if None).
        **kwargs: Passed to the ComboBox (e.g. ``label``).
    """

    def __init__(
        self,
        asset: Asset,
        default: str | None = None,
        suffixes: tuple[str, ...] | None = None,
        **kwargs,
    ):
        self._asset = asset
        self._default = default
        self._suffixes = suffixes
        super().__init__(choices=self._files, **kwargs)
        # magicgui has no placeholder for combo boxes
        self.native.setPlaceholderText(DOWNLOAD_MENU_HINT)
        self._select_default()

        # Kept as attribute: the filter must live as long as the dropdown
        self._first_show = _OnFirstShow(self.native, self._download)
        assets_updated.connect(self._refresh)

    def _files(self, _widget=None) -> tuple[str, ...]:
        if not self._asset.directory.is_dir():
            return ()
        return tuple(
            sorted(
                path.name
                for path in self._asset.directory.iterdir()
                if not path.name.startswith(".")
                and (self._suffixes is None or path.suffix in self._suffixes)
            )
        )

    def _download(self) -> None:
        ensure_assets([self._asset])

    def _select_default(self) -> None:
        if self._default in self.choices:
            self.value = self._default

    def _refresh(self) -> None:
        try:
            was_empty = not self.choices
            self.reset_choices()
            if was_empty:
                self._select_default()
        except RuntimeError:  # The widget was closed meanwhile
            assets_updated.disconnect(self._refresh)


class _OnFirstShow(QObject):
    """Calls ``callback`` the first time ``widget`` is shown."""

    def __init__(self, widget, callback):
        super().__init__(widget)
        self._callback = callback
        widget.installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.Show:
            obj.removeEventFilter(self)
            self._callback()
        return False
