from __future__ import annotations

import inspect
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from PySide6.QtCore import QObject, Signal, Slot, QThread, Qt, QSignalBlocker
from PySide6.QtWidgets import QProgressDialog

from config.constants import CANCELLED_MSG


def start_busy_job(
    parent,
    *,
    title: str,
    message: str,
    fn: Callable[..., Any],
    cancelable: bool = False,
    progress_total: Optional[int] = None,
) -> "BusyJob":
    return BusyJob(
        parent,
        title=title,
        message=message,
        fn=fn,
        cancelable=cancelable,
        progress_total=progress_total,
    ).start()


class BusyWorker(QObject):
    finished = Signal(object)
    error = Signal(str)
    progress = Signal(int, int, str)

    def __init__(
        self,
        fn: Callable[..., Any],
        total: Optional[int] = None,
        cancel_event: Optional[threading.Event] = None,
    ):
        super().__init__()
        self._fn = fn
        self._total = int(total or 0)
        self._cancel = cancel_event or threading.Event()

    def _progress_cb(self, current: int, total: Optional[int] = None, message: str = ""):
        if self._cancel.is_set():
            raise RuntimeError(CANCELLED_MSG)

        t = int(total) if total is not None else int(self._total)
        self.progress.emit(int(current), int(t), str(message or ""))

    @Slot()
    def run(self):
        try:
            sig = inspect.signature(self._fn)
            n_params = len(sig.parameters)

            if n_params >= 2:
                res = self._fn(self._progress_cb, self._cancel)
            elif n_params == 1:
                res = self._fn(self._progress_cb)
            else:
                res = self._fn()

            self.finished.emit(res)

        except Exception as e:
            msg = str(e).strip() or "Unknown error"
            # Preserve cancellation sentinel
            if msg == CANCELLED_MSG:
                self.error.emit(CANCELLED_MSG)
            else:
                self.error.emit(msg)


class BusyJob(QObject):
    finished = Signal(object)
    error = Signal(str)
    cancel_requested = Signal()

    def __init__(
        self,
        parent,
        *,
        title: str,
        message: str,
        fn: Callable[..., Any],
        cancelable: bool = False,
        progress_total: Optional[int] = None,
    ):
        super().__init__(parent)

        self._title = title
        self._message = message
        self._cancelable = bool(cancelable)
        self._progress_total = int(progress_total) if progress_total is not None else None

        # Cancel event shared with the worker
        self._cancel_event = threading.Event()

        # IMPORTANT: QProgressDialog parent must be a QWidget (MainWindow), not a QObject.
        # parent passed into BusyJob is MainWindow in your app.
        self.dialog = QProgressDialog(parent)
        self.dialog.setWindowTitle(title)
        self.dialog.setLabelText(message)
        self.dialog.setMinimumDuration(0)
        self.dialog.setWindowModality(Qt.WindowModality.ApplicationModal)

        if self._cancelable:
            self.dialog.setCancelButtonText("Cancel")
            self.dialog.canceled.connect(self._on_cancel)
        else:
            self.dialog.setCancelButton(None)

        if self._progress_total is not None and self._progress_total > 0:
            self.dialog.setRange(0, self._progress_total)
            self.dialog.setValue(0)
        else:
            # Indeterminate / spinner mode
            self.dialog.setRange(0, 0)

        # Use an un-parented thread to avoid parent/child + deleteLater redundancy.
        self.thread = QThread()
        self.worker = BusyWorker(fn, total=self._progress_total, cancel_event=self._cancel_event)
        self.worker.moveToThread(self.thread)

        # Canonical cleanup wiring: delete worker/thread when the thread ends.
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.deleteLater)

        # Run worker, marshal results back via signals (queued cross-thread).
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.error.connect(self._on_worker_error)

    def start(self):
        self.dialog.show()
        self.thread.start()
        return self

    @Slot(int, int, str)
    def _on_progress(self, current: int, total: int, message: str):
        if self.dialog is None:
            return

        if total and self.dialog.maximum() != total:
            self.dialog.setRange(0, total)

        if message:
            self.dialog.setLabelText(message)

        if self.dialog.maximum() > 0:
            self.dialog.setValue(max(0, min(int(current), int(self.dialog.maximum()))))

    @Slot(object)
    def _on_worker_finished(self, res: Any):
        self._close_and_delete_dialog()
        self.finished.emit(res)
        self._request_thread_quit()

    @Slot(str)
    def _on_worker_error(self, err_text: str):
        self._close_and_delete_dialog()
        self.error.emit(err_text)
        self._request_thread_quit()

    @Slot()
    def _on_cancel(self):
        # Idempotent
        if self._cancel_event.is_set():
            return

        self._cancel_event.set()
        self.cancel_requested.emit()

        # UI feedback
        try:
            if self.dialog is not None:
                self.dialog.setLabelText("Cancelling…")
                self.dialog.setCancelButton(None)
                self.dialog.setWindowTitle(self._title)
                self.dialog.show()
                self.dialog.raise_()
                self.dialog.activateWindow()
        except Exception:
            pass

    def _request_thread_quit(self):
        try:
            if self.thread is not None:
                self.thread.quit()
        except Exception:
            # Worst case: allow object graph to die; thread cleanup is still handled by Qt when possible.
            pass

    def _close_and_delete_dialog(self):
        dlg = getattr(self, "dialog", None)
        if dlg is None:
            return

        try:
            # Prevent close() from emitting canceled() and causing spurious cancellation flow
            blocker = QSignalBlocker(dlg)
            if dlg.maximum() > 0:
                dlg.setValue(dlg.maximum())
            dlg.close()
            del blocker
        except Exception:
            pass

        try:
            dlg.deleteLater()
        except Exception:
            pass

        self.dialog = None


@dataclass
class JobRunner:
    parent: Any
    _jobs: list = field(default_factory=list)

    def run(
        self,
        title: str,
        message: str,
        fn: Callable[..., Any],
        on_done: Optional[Callable[[Any], None]] = None,
        on_err: Optional[Callable[[str], None]] = None,
        cancelable: bool = False,
        progress_total: Optional[int] = None,
    ):
        job = start_busy_job(
            self.parent,
            title=title,
            message=message,
            fn=fn,
            cancelable=cancelable,
            progress_total=progress_total,
        )
        self._jobs.append(job)

        def forget(*_):
            if job in self._jobs:
                self._jobs.remove(job)

        job.finished.connect(forget)
        job.error.connect(forget)

        if on_done:
            job.finished.connect(on_done)
        if on_err:
            job.error.connect(on_err)

        return job