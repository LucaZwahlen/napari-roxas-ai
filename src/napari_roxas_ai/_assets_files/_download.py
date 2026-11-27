import os
import shutil
import tempfile
import zipfile
from collections.abc import Generator, Iterable
from pathlib import Path

import requests

from napari_roxas_ai._jobs import Message, Progress

from ._registry import ASSET_ID_FILE, Asset

REPO = "roxas-ai/napari-roxas-ai"
RELEASES_URL = f"https://api.github.com/repos/{REPO}/releases"
MB = 1024 * 1024
CHUNK_SIZE = 5 * MB


def download_assets(assets: Iterable[Asset]):
    """
    Job operation: download and install the given assets that are missing.

    Each asset ends up installed or with a warning saying why not (e.g.
    GitHub is not reachable, or the release lacks a required file: a release
    already installed is then not downloaded again). Each archive is downloaded to a temporary directory and only installed
    once complete, so a cancelled or failed download leaves nothing behind.
    """
    # Look up all archives first: their size is the progress total
    to_download = []
    for asset in assets:
        if asset.is_available():  # E.g. downloaded for an earlier request
            continue
        release_asset = yield from _release_asset_to_download(asset)
        if release_asset is not None:
            to_download.append((asset, release_asset))

    total = sum(release_asset["size"] for _, release_asset in to_download)
    done = 0
    for asset, release_asset in to_download:
        label = asset.label.lower()
        with tempfile.TemporaryDirectory() as temp_dir:
            archive = Path(temp_dir) / asset.archive
            try:
                for chunk_size in _stream(
                    release_asset["browser_download_url"], archive
                ):
                    done += chunk_size
                    yield Progress(
                        done,
                        total,
                        f"Downloading {label} "
                        f"({done / MB:.1f}/{total / MB:.1f} MB)",
                    )
            except requests.RequestException as e:
                yield Message(
                    f"Could not download the {label} ({e}).", level="warning"
                )
                continue
            yield Progress(done, total, f"Installing {label}...")
            _install(archive, asset, release_asset["id"])
        if asset.missing():
            yield _not_in_release(asset)


def _release_asset_to_download(asset: Asset):
    """
    The GitHub asset to download for ``asset``, or None after a warning
    saying why there is none.
    """
    label = asset.label.lower()
    try:
        release_asset = _find_in_releases(asset.archive)
    except ConnectionError as e:
        yield Message(
            f"Could not download the {label} ({e}).", level="warning"
        )
        return None
    if release_asset is None:
        yield Message(
            f"Could not download the {label}: {asset.archive} is in no "
            "release.",
            level="warning",
        )
        return None
    if asset.installed_id() == str(release_asset["id"]):
        yield _not_in_release(asset)
        return None
    return release_asset


def _not_in_release(asset: Asset) -> Message:
    return Message(
        f"The release does not contain {', '.join(asset.missing())} "
        f"({asset.label.lower()}).",
        level="warning",
    )


def _find_in_releases(archive: str) -> dict | None:
    """
    The GitHub asset ``archive`` of the release matching the installed plugin
    version, or of the latest release if that one is missing or lacks it.

    Returns:
        The GitHub asset (with "id", "size" and "browser_download_url"),
        None if neither release contains ``archive``.
    Raises:
        ConnectionError: GitHub is not reachable.
    """
    from napari_roxas_ai import __version__

    for url in (
        f"{RELEASES_URL}/tags/v{__version__}",
        f"{RELEASES_URL}/latest",
    ):
        release = _get_release(url) or {}
        for release_asset in release.get("assets", []):
            if release_asset["name"] == archive:
                return release_asset
    return None


def _get_release(url: str) -> dict | None:
    """The release at ``url``, None if there is no such release."""
    try:
        response = requests.get(url, headers=_headers(), timeout=10)
        if response.status_code == 404:
            return None
        response.raise_for_status()
    except requests.RequestException as e:
        raise ConnectionError(
            f"Cannot access the GitHub releases ({e}). Please check your "
            "internet connection."
        ) from e
    return response.json()


def _headers() -> dict:
    """Authenticate with GITHUB_TOKEN if set (higher API rate limit)."""
    token = os.environ.get("GITHUB_TOKEN")
    return {"Authorization": f"Bearer {token}"} if token else {}


def _stream(url: str, target: Path) -> Generator[int, None, None]:
    """Download ``url`` to ``target``, yielding the size of each chunk."""
    with requests.get(
        url, headers=_headers(), stream=True, timeout=30
    ) as response:
        response.raise_for_status()
        with open(target, "wb") as file:
            for chunk in response.iter_content(CHUNK_SIZE):
                file.write(chunk)
                yield len(chunk)


def _install(archive: Path, asset: Asset, release_asset_id: int) -> None:
    """
    Put the content of the zip ``archive`` in the asset's directory,
    replacing files already there (e.g. models kept from a previous release),
    and remember which release asset it came from.

    The release archives hold a single root folder, whose content is
    installed.
    """
    extracted = archive.parent / "extracted"
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(extracted)
    entries = list(extracted.iterdir())
    root = (
        entries[0] if len(entries) == 1 and entries[0].is_dir() else extracted
    )

    asset.directory.mkdir(parents=True, exist_ok=True)
    for item in root.iterdir():
        target = asset.directory / item.name
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
        shutil.move(str(item), str(target))
    (asset.directory / ASSET_ID_FILE).write_text(str(release_asset_id))
