"""
ModernAnnotationGUI: Main orchestrator for point cloud annotation.
Initializes Tkinter window, applies theme, registers global shortcuts,
assembles domain components, and manages async execution & graceful exit.
"""
import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog
from gui.theme import COLORS, apply_theme
from gui.components.cloud_info_view import CloudInfoView
from gui.components.classification_view import ClassificationView
from gui.components.rendering_view import RenderingView
from gui.components.ai_tools_view import AiToolsView
from gui.components.storage_io_view import StorageIoView
from gui.components.status_bar_view import StatusBarView
from gui.modals.advances import AdvancesDialog
from gui.modals.shortcuts import ShortcutsDialog
from gui.services.shortcut_manager import ShortcutManager

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

        # Initialize Shortcut Manager
        self.shortcut_manager = ShortcutManager()

        # Global Keyboard Shortcuts
        self.root.bind('<Control-z>', lambda e: self.undo_action())
        self.root.bind('<Control-Z>', lambda e: self.undo_action())
        self.root.bind('<Control-y>', lambda e: self.redo_action())
        self.root.bind('<Control-Y>', lambda e: self.redo_action())

        # Window close handler
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Build UI layout with domain components
        self._create_widgets()

        # Bind classification shortcuts and update button state
        self.apply_shortcuts()

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
        """Fetch PointCloud stats and update [INFO] view and [RENDER & CAMERA] controls."""
        if self.pc:
            stats = self.pc.get_stats()
            if hasattr(self, 'cloud_info_view'):
                self.cloud_info_view.update_stats(stats)
            if hasattr(self, 'rendering_view'):
                self.rendering_view.update_point_size(stats.get('point_size'))

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

    # ------------------ Shortcuts Handling ------------------
    def apply_shortcuts(self):
        """Bind active shortcuts to root window and refresh UI labels."""
        self.shortcut_manager.apply_bindings(self.root, self.on_shortcut_triggered)
        if hasattr(self, 'classification_view'):
            count = len(self.shortcut_manager.key_to_class)
            if self.shortcut_manager.enabled and count > 0:
                self.classification_view.shortcuts_btn.configure(text="Shortcuts ({})".format(count))
            else:
                self.classification_view.shortcuts_btn.configure(text="Shortcuts (Off)")
            # Refresh combobox entries with [Key] prefix
            self.classification_view.refresh_combobox_items()

    def on_shortcut_triggered(self, class_name, key_pressed):
        """Invoked when a registered shortcut key is pressed."""
        if not hasattr(self, 'classification_view'):
            return

        # 1. Update combobox selection
        self.classification_view.set_selected_class(class_name)

        # 2. If points are selected in viewer, execute classification immediately
        if self.pc and self.pc.has_selection():
            self.classification_view.execute_selection()
        else:
            self.log_message("Shortcut [{}]: Selected '{}' (Use Ctrl+Click to select points, then re-press key)".format(
                key_pressed.upper(), class_name
            ), "INFO")

    def open_shortcuts_modal(self):
        """Open the shortcuts customization dialog."""
        try:
            ShortcutsDialog(self.root, self.shortcut_manager, on_applied_callback=self.apply_shortcuts)
        except Exception as e:
            self.log_message("Error opening shortcuts modal: {}".format(e), "ERROR")

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

    def open_ply_dialog(self):
        """Open a file dialog to select and load any PLY point cloud file."""
        initial_dir = os.path.dirname(self.pc.filename) if self.pc and self.pc.filename else os.getcwd()
        filepath = filedialog.askopenfilename(
            parent=self.root,
            title="Open PLY Point Cloud",
            initialdir=initial_dir,
            filetypes=[("PLY Point Cloud", "*.ply"), ("All Files", "*.*")]
        )
        if not filepath:
            return

        def task():
            self.pc.reload_from_file(filepath, preserve_camera=False, is_new_base=True)
            return filepath

        def on_done(loaded_path):
            self.on_cloud_reloaded(loaded_path)
            self.log_message("Opened point cloud: {}".format(os.path.basename(loaded_path)), "SUCCESS")

        self.run_async(
            task,
            start_msg="Loading point cloud '{}'...".format(os.path.basename(filepath)),
            success_msg="Point cloud loaded successfully",
            on_success=on_done
        )

    def run(self):
        """Start the Tkinter main event loop."""
        self.root.mainloop()

