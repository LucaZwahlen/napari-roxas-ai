from qtpy.QtWidgets import QDialog, QVBoxLayout, QWidget

from napari_roxas_ai._job_runner import JobHandle, JobProgressPanel


class AssetsDownloadDialog(QDialog):
    """
    Modal dialog showing the progress of a download job.

    It closes itself when the job is finished. Closing it (window button,
    Escape) cancels the job, like its Cancel button.
    """

    def __init__(self, handle: JobHandle, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Downloading assets")
        self.setModal(True)
        self.setMinimumWidth(450)
        self._handle = handle

        self._panel = JobProgressPanel()
        layout = QVBoxLayout(self)
        layout.addWidget(self._panel.native)
        # Only tracked (and so shown) once it has a parent: Qt would open
        # the panel as a window of its own
        self._panel.track(handle)
        handle.connect(on_finished=self._on_finished)

    def _on_finished(self, _handle: JobHandle) -> None:
        self.accept()

    def reject(self) -> None:
        if self._handle.is_running:
            # Closed once the job stopped, see _on_finished
            self._panel.cancel()
        else:
            super().reject()
