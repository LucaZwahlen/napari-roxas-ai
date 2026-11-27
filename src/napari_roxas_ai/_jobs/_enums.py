from enum import Enum


class JobStatus(Enum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def is_done(self) -> bool:
        return self in (
            JobStatus.SUCCEEDED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
        )


class JobTag(Enum):

    LOADING = "loading"
    SAVING = "saving"
    PREPARATION = "preparation"
    SEGMENTATION = "segmentation"
    MEASUREMENTS = "measurements"
    VECTORIZATION = "vectorization"
    RINGS_RERUN = "rings_rerun"
    ASSETS_DOWNLOAD = "assets_download"


def as_tags(tags) -> frozenset[JobTag]:
    """Validate ``tags`` as JobTag members; raise TypeError otherwise."""
    tags = frozenset(tags)
    invalid = [tag for tag in tags if not isinstance(tag, JobTag)]
    if invalid:
        raise TypeError(f"Job tags must be JobTag members, got {invalid!r}")
    return tags
