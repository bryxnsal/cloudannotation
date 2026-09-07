"""
BaseComponent for all GUI subviews.
Provides unified access to main app context, PointCloud and async helpers.
"""
from tkinter import ttk
from gui.theme import COLORS

class BaseComponent(ttk.Frame):
    """
    Abstract base component providing convenient delegation methods.
    """
    def __init__(self, parent, app, pc, **kwargs):
        super().__init__(parent, style='Modern.TFrame', **kwargs)
        self.app = app
        self.pc = pc
        self.colors = COLORS

    def run_async(self, target_fn, start_msg=None, success_msg=None, on_success=None):
        """Delegate async background task to main app orchestrator."""
        return self.app.run_async(target_fn, start_msg=start_msg, success_msg=success_msg, on_success=on_success)

    def log_message(self, message, level="INFO"):
        """Delegate log message to main status bar and log panel."""
        return self.app.log_message(message, level=level)

    def update_cloud_info(self):
        """Delegate cloud info update to main app."""
        return self.app.update_cloud_info()
