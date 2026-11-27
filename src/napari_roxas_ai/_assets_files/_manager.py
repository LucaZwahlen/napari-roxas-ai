import threading
from collections.abc import Callable, Iterable

import napari
from napari.utils.notifications import show_info
from psygnal import SignalInstance

from napari_roxas_ai._job_runner import get_runner
from napari_roxas_ai._jobs import Job, JobTag, Partial

from ._dialog import AssetsDownloadDialog
from ._download import download_assets
from ._registry import ALL_ASSETS, Asset

# Emitted after each download job, whatever its outcome, so that widgets
# listing assets can refresh their choices
assets_updated = SignalInstance()


def ensure_assets(
    assets: Iterable[Asset], on_done: Callable[[bool], None] | None = None
) -> None:
    """
    Download the given assets that are missing.

    There is at most one download job, shown in a modal "Downloading assets"
    dialog that can cancel it. A request made while it runs is added to its
    queue, and answered once its own assets are processed.

    Args:
        assets: The assets needed.
        on_done: Called (in the GUI thread) with whether all assets are
            available, right away if they are already. Each asset that is
            not got a warning saying why, unless the download was cancelled.
    """
    global _download_job
    request = _Request(list(assets), on_done)
    _remove_stale_archives(request.assets)
    if all(asset.is_available() for asset in request.assets):
        request.answer()
        return
    if _download_job is not None and _download_job.add(request):
        return

    _download_job = _DownloadJob(request)
    handle = get_runner().submit(
        Job(
            "Downloading assets",
            _download_job.run,
            tags={JobTag.ASSETS_DOWNLOAD},
        ),
        on_partial=_Request.answer,
        on_finished=_download_job.finished,
    )
    if handle.is_running:
        # Kept alive by the handle until the job is finished
        AssetsDownloadDialog(handle, parent=_main_window()).open()


def download_missing_assets() -> None:
    """
    Menu command (File > IO Utilities): download every missing asset, e.g.
    after a download failed or was cancelled.
    """
    if all(asset.is_available() for asset in ALL_ASSETS):
        show_info("All ROXAS AI assets are already downloaded.")
        return
    ensure_assets(ALL_ASSETS)


class _Request:
    """One call of ensure_assets."""

    def __init__(self, assets: list[Asset], on_done: Callable | None):
        self.assets = assets
        self._on_done = on_done
        self._answered = False

    def answer(self) -> None:
        """Call on_done with whether the assets are available (only once)."""
        if self._answered:
            return
        self._answered = True
        if self._on_done is not None:
            self._on_done(all(asset.is_available() for asset in self.assets))


class _DownloadJob:
    """
    The requests of a download job, processed in order until none are left.

    Requests are added in the GUI thread while the job takes them in its
    worker thread. Once it took its last one (or stopped), it is closed:
    nothing can be added anymore and the next request starts a new job.
    """

    def __init__(self, first_request: _Request):
        self._lock = threading.Lock()
        self._queue = [first_request]
        self._closed = False
        self._requests = [first_request]  # Only used in the GUI thread

    def add(self, request: _Request) -> bool:
        """Queue ``request``; False if the job is closed."""
        with self._lock:
            if self._closed:
                return False
            self._queue.append(request)
        self._requests.append(request)
        return True

    def run(self):
        """Job operation."""
        try:
            while (request := self._next()) is not None:
                yield from download_assets(request.assets)
                yield Partial(request)  # Answered in the GUI thread
        finally:
            # Also when cancelled or failed
            with self._lock:
                self._closed = True

    def finished(self, _handle) -> None:
        assets_updated.emit()
        # The requests not processed because the job was cancelled or failed
        for request in self._requests:
            request.answer()

    def _next(self) -> _Request | None:
        with self._lock:
            if not self._queue:
                self._closed = True
                return None
            return self._queue.pop(0)


_download_job: _DownloadJob | None = None


def _remove_stale_archives(assets: list[Asset]) -> None:
    """Remove an archive left behind by a failed download of version 0.2.0."""
    for asset in assets:
        stale = asset.directory / asset.archive
        if stale.is_file():
            stale.unlink()


def _main_window():
    """The napari window, the parent of the dialog (None without viewer)."""
    viewer = napari.current_viewer()
    return viewer.window._qt_window if viewer is not None else None
