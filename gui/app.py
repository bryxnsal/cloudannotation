"""
ModernAnnotationGUI: Main orchestrator for point cloud annotation.
Initializes Tkinter window, applies theme, registers global shortcuts,
assembles domain components, and manages async execution & graceful exit.
"""
import os
import threading
import tkinter as tk
from tkinter import ttk
from gui.theme import COLORS, apply_theme
from gui.components.cloud_info_view import CloudInfoView
from gui.components.classification_view import ClassificationView
from gui.components.rendering_view import RenderingView
from gui.components.ai_tools_view import AiToolsView
from gui.components.storage_io_view import StorageIoView
from gui.components.status_bar_view import StatusBarView
from gui.modals.advances import AdvancesDialog

class ModernAnnotationGUI:
    """
    Main application window and coordinator.
    """
    def __init__(self, pc):
        self.root = tk.Tk()
        self.root.title("Point Cloud Annotator")
        self.root.geometry("520x720")
        self.root.configure(bg=COLORS['bg_primary'])

        # Always on top
        self.root.attributes('-topmost', True)

        self.pc = pc
        self.colors = COLORS

        # Apply styles and theme
        self.style = apply_theme(self.root)

        # Global Keyboard Shortcuts
        self.root.bind('<Control-z>', lambda e: self.undo_action())
        self.root.bind('<Control-Z>', lambda e: self.undo_action())
        self.root.bind('<Control-y>', lambda e: self.redo_action())
        self.root.bind('<Control-Y>', lambda e: self.redo_action())

        # Window close handler
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Build UI layout with domain components
        self._create_widgets()

        # Initialize info display & initial log
        self.update_cloud_info()
        self.log_message("System initialized", "INFO")

    def on_close(self):
        """Handle window closing gracefully."""
        try:
            if self.pc:
                self.pc.close_viewer()
        except Exception:
            pass
        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass
        os._exit(0)

    def _create_widgets(self):
        """Assemble all modular domain components into the main container."""
        main_frame = ttk.Frame(self.root, style='Modern.TFrame')
        main_frame.pack(fill='both', expand=True, padx=12, pady=12)

        # 1. [INFO] Section
        self.cloud_info_view = CloudInfoView(main_frame, self, self.pc)
        self.cloud_info_view.pack(fill='x', pady=(0, 8))

        # 2. [CLASS] Section
        self.classification_view = ClassificationView(main_frame, self, self.pc)
        self.classification_view.pack(fill='x', pady=(0, 8))

        # 3. [AI TOOLS] Section
        self.ai_tools_view = AiToolsView(main_frame, self, self.pc)
        self.ai_tools_view.pack(fill='x', pady=(0, 8))

        # 4. [RENDER & CAMERA] Section
        self.rendering_view = RenderingView(main_frame, self, self.pc)
        self.rendering_view.pack(fill='x', pady=(0, 8))

        # 5. [I/O] Section
        self.storage_io_view = StorageIoView(main_frame, self, self.pc)
        self.storage_io_view.pack(fill='x', pady=(0, 8))

        # 6. Status, Progress Bar & Logs Section
        self.status_bar_view = StatusBarView(main_frame, self, self.pc)
        self.status_bar_view.pack(fill='x', pady=(2, 0))

    # ------------------ Shortcuts / Delegations ------------------
    def undo_action(self):
        self.classification_view.undo_action()

    def redo_action(self):
        self.classification_view.redo_action()

    def log_message(self, message, level="INFO"):
        self.status_bar_view.log_message(message, level=level)

    def update_cloud_info(self):
        """Fetch PointCloud stats and update [INFO] view."""
        if hasattr(self, 'cloud_info_view') and self.pc:
            stats = self.pc.get_stats()
            self.cloud_info_view.update_stats(stats)

    # ------------------ Progress Bar Helpers ------------------
    def start_progress(self, message=None):
        self.status_bar_view.start_progress(message)

    def stop_progress(self, message=None, level="SUCCESS"):
        self.status_bar_view.stop_progress(message, level=level)

    def set_progress(self, value, maximum=100, message=None):
        self.status_bar_view.set_progress(value, maximum, message)

    # ------------------ Async Worker Runner ------------------
    def run_async(self, target_fn, start_msg=None, success_msg=None, on_success=None):
        """Run tasks in background thread with smooth progress animation."""
        def worker():
            try:
                res = target_fn()
                def on_done():
                    if on_success:
                        on_success(res)
                    self.stop_progress(success_msg, "SUCCESS")
                self.root.after(0, on_done)
            except Exception as e:
                err_msg = str(e)
                self.root.after(0, lambda: self.stop_progress("Error: {}".format(err_msg), "ERROR"))

        self.start_progress(start_msg)
        t = threading.Thread(target=worker, daemon=True)
        t.start()

    # ------------------ Modal Launchers ------------------
    def open_advances_modal(self):
        """Open the Advances List modal dialog."""
        try:
            AdvancesDialog(self.root, self.pc, on_reload_callback=self.on_cloud_reloaded)
        except Exception as e:
            self.log_message("Error opening advances modal: {}".format(e), "ERROR")

    def on_cloud_reloaded(self, filepath):
        """Callback invoked when an advance or base file is reloaded into PointCloud."""
        if hasattr(self, 'rendering_view'):
            self.rendering_view.select_btn.configure(text="Select")
        self.update_cloud_info()
        import datetime
        self.log_message("Loaded point cloud: {}".format(datetime.datetime.now().strftime('%H:%M:%S')), "SUCCESS")

    def run(self):
        """Start the Tkinter main event loop."""
        self.root.mainloop()
