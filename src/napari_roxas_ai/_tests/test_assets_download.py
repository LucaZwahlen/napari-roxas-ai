"""
Missing assets (models, sample data) are downloaded from the GitHub releases.
"""

import dataclasses
import io
import zipfile

import pytest
import requests

from napari_roxas_ai._assets_files import (
    Asset,
    _download,
    _manager,
    download_missing_assets,
    ensure_assets,
)
from napari_roxas_ai._assets_files._download import download_assets
from napari_roxas_ai._jobs import Job, JobStatus, run_job_sync


def zip_archive(files: dict, root: str = "archive") -> bytes:
    """A zip archive with a root folder, as published in the releases."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, content in files.items():
            zf.writestr(f"{root}/{name}", content)
    return buffer.getvalue()


class _Response:
    def __init__(self, status_code=200, json=None, content=b""):
        self.status_code = status_code
        self._json = json
        self._content = content

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")

    def iter_content(self, chunk_size=1):
        # Small chunks, so that a download can be cancelled half way
        for start in range(0, len(self._content), 1024):
            yield self._content[start : start + 1024]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeGitHub:
    """
    The GitHub releases of the plugin, served from memory.

    ``publish(tag, archive, files)`` adds an archive to a release, the last
    published release being the latest one. ``downloads`` lists the archives
    downloaded; ``offline = True`` makes every request fail.
    """

    def __init__(self):
        self.releases: dict[str, list[dict]] = {}
        self.latest: str | None = None
        self.downloads: list[str] = []
        self.offline = False
        self._contents: dict[str, bytes] = {}

    def publish(self, tag: str, archive: str, files: dict) -> None:
        url = f"https://example.org/{tag}/{archive}"
        content = zip_archive(files, root=archive.removesuffix(".zip"))
        self._contents[url] = content
        self.releases.setdefault(tag, []).append(
            {
                "name": archive,
                "id": len(self._contents),
                "size": len(content),
                "browser_download_url": url,
            }
        )
        self.latest = tag

    def get(self, url, **kwargs):
        if self.offline:
            raise requests.ConnectionError("offline")
        if url in self._contents:
            self.downloads.append(url.rsplit("/", 1)[-1])
            return _Response(content=self._contents[url])
        tag = (
            self.latest if url.endswith("/latest") else url.rsplit("/", 1)[-1]
        )
        if tag not in self.releases:
            return _Response(status_code=404)
        return _Response(json={"tag_name": tag, "assets": self.releases[tag]})


@pytest.fixture
def fake_github(monkeypatch):
    from napari_roxas_ai._assets_files import _download

    github = FakeGitHub()
    monkeypatch.setattr(_download.requests, "get", github.get)
    return github


@pytest.fixture
def installed_tag():
    """The release tag matching the installed plugin version."""
    from napari_roxas_ai import __version__

    return f"v{__version__}"


@pytest.fixture
def asset(tmp_path):
    return Asset(
        label="Ring models",
        archive="rings_models.zip",
        directory=tmp_path / "_rings",
        required=("old_model.pth", "new_model.pt"),
    )


RELEASE_FILES = {"old_model.pth": b"release weights", "new_model.pt": b"new"}


def _ensure(asset) -> bool:
    """Whether the asset is available once ensure_assets is done."""
    results = []
    ensure_assets([asset], results.append)
    (available,) = results
    return available


def test_missing_assets_come_from_the_installed_version_release(
    asset, sync_runner, fake_github, installed_tag
):
    fake_github.publish(installed_tag, asset.archive, RELEASE_FILES)
    fake_github.publish("v99.0.0", asset.archive, {"old_model.pth": b"newer"})

    assert _ensure(asset) is True
    assert (
        asset.directory / "old_model.pth"
    ).read_bytes() == b"release weights"


@pytest.mark.parametrize("version_release", ["missing", "without archive"])
def test_latest_release_is_used_when_the_version_release_lacks_the_assets(
    asset, sync_runner, fake_github, installed_tag, version_release
):
    if version_release == "without archive":
        fake_github.publish(installed_tag, "sample_data.zip", {"a.txt": b""})
    fake_github.publish("v99.0.0", asset.archive, RELEASE_FILES)

    assert _ensure(asset) is True
    assert asset.is_available()


def test_present_assets_are_not_downloaded(asset, sync_runner, fake_github):
    asset.directory.mkdir()
    for name in asset.required:
        (asset.directory / name).write_bytes(b"weights")
    fake_github.offline = True  # Any request would fail

    assert _ensure(asset) is True


def test_existing_installation_is_completed(
    asset, sync_runner, fake_github, installed_tag
):
    asset.directory.mkdir()
    (asset.directory / "old_model.pth").write_bytes(b"old weights")
    # Archive left behind by a failed download of version 0.2.0
    (asset.directory / asset.archive).write_bytes(b"stale archive")
    fake_github.publish(installed_tag, asset.archive, RELEASE_FILES)

    assert _ensure(asset) is True
    assert (
        asset.directory / "old_model.pth"
    ).read_bytes() == b"release weights"
    assert not (asset.directory / asset.archive).exists()


def test_release_lacking_a_required_file_is_downloaded_only_once(
    asset, sync_runner, fake_github, installed_tag, monkeypatch
):
    from napari_roxas_ai._job_runner import _runner

    warnings = []
    monkeypatch.setattr(_runner, "show_warning", warnings.append)
    fake_github.publish(
        installed_tag, asset.archive, {"old_model.pth": b"weights"}
    )

    # Each attempt tells which file the release lacks
    assert _ensure(asset) is False
    assert len(warnings) == 1 and "new_model.pt" in warnings[0]
    assert _ensure(asset) is False
    assert len(warnings) == 2 and "new_model.pt" in warnings[1]
    assert fake_github.downloads == [asset.archive]
    # What the release has is installed and usable
    assert (asset.directory / "old_model.pth").exists()


def test_offline_keeps_the_files_present(asset, sync_runner, fake_github):
    asset.directory.mkdir()
    (asset.directory / "old_model.pth").write_bytes(b"weights")
    fake_github.offline = True

    assert _ensure(asset) is False
    assert (asset.directory / "old_model.pth").read_bytes() == b"weights"


def test_offline_without_files_reports_unavailable(
    asset, sync_runner, fake_github
):
    fake_github.offline = True

    assert _ensure(asset) is False


def test_cancelled_download_leaves_nothing_behind(
    asset, fake_github, installed_tag
):
    # Large enough to be downloaded in several chunks
    fake_github.publish(
        installed_tag,
        asset.archive,
        {**RELEASE_FILES, "big.bin": bytes(range(256)) * 64},
    )
    asset.directory.mkdir()
    (asset.directory / "old_model.pth").write_bytes(b"old weights")

    events = []
    outcome = run_job_sync(
        Job("download", download_assets, args=([asset],)),
        on_event=events.append,
        should_cancel=lambda: bool(events),
    )

    assert outcome.status is JobStatus.CANCELLED
    assert [p.name for p in asset.directory.iterdir()] == ["old_model.pth"]
    assert (asset.directory / "old_model.pth").read_bytes() == b"old weights"


def test_requests_during_a_download_are_answered_once_their_assets_are(
    asset, tmp_path, sync_runner, fake_github, installed_tag, monkeypatch
):
    other = dataclasses.replace(
        asset,
        label="Sample data",
        archive="sample.zip",
        directory=tmp_path / "sample",
        required=("scan.jpg",),
    )
    fake_github.publish(installed_tag, asset.archive, RELEASE_FILES)
    fake_github.publish(installed_tag, other.archive, {"scan.jpg": b"scan"})
    events = []

    # While the first asset downloads, the second one and the first one
    # again are requested
    get = fake_github.get

    def get_and_request(url, **kwargs):
        if url.endswith(".zip"):
            events.append(f"download {url.rsplit('/', 1)[-1]}")
            if len(events) == 1:
                ensure_assets([other], lambda ok: events.append(("2", ok)))
                ensure_assets([asset], lambda ok: events.append(("3", ok)))
        return get(url, **kwargs)

    monkeypatch.setattr(_download.requests, "get", get_and_request)
    ensure_assets([asset], lambda ok: events.append(("1", ok)))

    assert events == [
        f"download {asset.archive}",
        ("1", True),
        f"download {other.archive}",
        ("2", True),
        ("3", True),
    ]


def test_menu_downloads_the_missing_assets_once(
    asset, sync_runner, fake_github, installed_tag, monkeypatch
):
    monkeypatch.setattr(_manager, "ALL_ASSETS", (asset,))
    fake_github.publish(installed_tag, asset.archive, RELEASE_FILES)

    download_missing_assets()
    download_missing_assets()

    assert asset.is_available()
    assert fake_github.downloads == [asset.archive]
