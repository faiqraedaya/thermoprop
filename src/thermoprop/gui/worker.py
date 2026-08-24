"""
Background work and the busy state that goes with it.

A calculation that takes more than a moment must not freeze the window, and
the user must be able to see that something is running. ``run_async`` pairs
those two things: the triggering controls go disabled, the status bar shows
an indeterminate bar immediately (never animated into place), and both are
released on completion whether the work succeeded or failed.
"""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QWidget


class Worker(QThread):
    """Runs one callable off the GUI thread and reports the outcome."""

    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self):
        try:
            self.done.emit(self._fn(*self._args, **self._kwargs))
        except Exception as e:            # reported to the user, not swallowed
            self.failed.emit(str(e))


def host_window(widget: QWidget):
    """The main window above this widget, if it exposes the busy protocol."""
    window = widget.window()
    return window if hasattr(window, "set_busy") else None


class BusyGuard:
    """Disables the controls that trigger a computation while it runs."""

    def __init__(self, owner: QWidget, controls, message: str = ""):
        self._owner = owner
        self._controls = [c for c in controls if c is not None]
        self._message = message

    def start(self):
        for control in self._controls:
            control.setEnabled(False)
        window = host_window(self._owner)
        if window is not None:
            window.set_busy(True, self._message)

    def stop(self, message: str = ""):
        for control in self._controls:
            control.setEnabled(True)
        window = host_window(self._owner)
        if window is not None:
            window.set_busy(False, message)
