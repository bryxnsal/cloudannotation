"""
AdvancesDialog: Main controller window (tk.Toplevel) for advances management.
Assembles AdvancesService, AdvancesTableView and AdvancesActionsView.
"""
import os
import tkinter as tk
from tkinter import ttk, messagebox
from gui.theme import COLORS
from gui.modals.advances.advances_service import AdvancesService
from gui.modals.advances.advances_table_view import AdvancesTableView
from gui.modals.advances.advances_actions_view import AdvancesActionsView

class AdvancesDialog(tk.Toplevel):
    """
    Modal dialog window to inspect, compare, load, overwrite and restore point cloud advances.
    """
    def __init__(self, parent, pc, on_reload_callback=None):
        super().__init__(parent)
        self.pc = pc
        self.on_reload_callback = on_reload_callback
        self.service = AdvancesService(pc)

        self.title("Advances Management - Point Cloud")
        self.geometry("860x500")
        self.minsize(750, 400)
        self.configure(bg=COLORS['bg_primary'])

        # Modal configuration
        self.transient(parent)
        self.grab_set()

        self._setup_ui()
        self.refresh_advances()

    def _setup_ui(self):
        # 1. Header Frame
        header_frame = ttk.Frame(self, style='Modern.TFrame')
        header_frame.pack(fill='x', padx=12, pady=(10, 6))

        base_name = os.path.basename(self.pc.filename) if self.pc.filename else "Unknown"
        title_lbl = ttk.Label(
            header_frame,
            text="Advances History for: {}".format(base_name),
            style='Title.TLabel',
            font=('Segoe UI', 11, 'bold')
        )
        title_lbl.pack(side='left')

        self.summary_lbl = ttk.Label(
            header_frame,
            text="",
            style='Modern.TLabel',
            font=('Segoe UI', 9)
        )
        self.summary_lbl.pack(side='right')

        # 2. Table View (Treeview)
        table_container = ttk.Frame(self, style='Modern.TFrame')
        table_container.pack(fill='both', expand=True, padx=12, pady=4)

        self.table_view = AdvancesTableView(
            table_container,
            on_double_click=self.load_advance_in_viewer
        )
        self.table_view.pack(fill='both', expand=True)

        # 3. Actions View (Toolbar)
        self.actions_view = AdvancesActionsView(
            self,
            on_load=self.load_advance_in_viewer,
            on_overwrite=self.overwrite_base_ply,
            on_restore=self.restore_base_ply,
            on_refresh=self.refresh_advances,
            on_close=self.destroy
        )
        self.actions_view.pack(fill='x', padx=12, pady=(8, 12))

    def refresh_advances(self):
        """Fetch latest advances via service and update table & summary."""
        advances_list, summary = self.service.list_advances()
        self.table_view.populate(advances_list)
        self.summary_lbl.config(text=summary)

    def load_advance_in_viewer(self):
        """Load selected advance into working memory and viewer."""
        advance = self.table_view.get_selected_advance()
        if not advance:
            messagebox.showwarning("Selection Required", "Please select an advance from the list.", parent=self)
            return

        try:
            self.service.load_advance_into_viewer(advance)
            if self.on_reload_callback:
                self.on_reload_callback(advance['filepath'])

            messagebox.showinfo(
                "Advance Loaded",
                "Successfully loaded advance:\n'{}'\ninto viewer.\n\n"
                "You can continue labeling and use 'Save Advance' to save further progress.".format(advance['filename']),
                parent=self
            )
        except Exception as e:
            messagebox.showerror("Error Loading Advance", "Failed to load advance: {}".format(e), parent=self)

    def overwrite_base_ply(self):
        """Overwrite base PLY file with selected advance."""
        advance = self.table_view.get_selected_advance()
        if not advance:
            messagebox.showwarning("Selection Required", "Please select an advance from the list.", parent=self)
            return

        base_path = self.pc.filename
        if not base_path or not os.path.isfile(base_path):
            messagebox.showerror("Base File Not Found", "Could not locate the base PLY file.", parent=self)
            return

        confirm = messagebox.askyesno(
            "Confirm Overwrite",
            "Are you sure you want to overwrite the base file:\n'{}'\n\n"
            "with advance:\n'{}'?\n\n"
            "A safety backup (.bak) of the current base file will be created automatically.".format(
                os.path.basename(base_path), advance['filename']
            ),
            parent=self
        )
        if not confirm:
            return

        try:
            base_file, bak_file = self.service.overwrite_base_ply(advance)
            if self.on_reload_callback:
                self.on_reload_callback(base_file)

            self.refresh_advances()
            messagebox.showinfo(
                "Base PLY Overwritten",
                "Base file '{}' has been overwritten successfully.\n"
                "Safety backup created at '{}'.".format(os.path.basename(base_file), os.path.basename(bak_file)),
                parent=self
            )
        except Exception as e:
            messagebox.showerror("Overwrite Error", "Failed to overwrite base file: {}".format(e), parent=self)

    def restore_base_ply(self):
        """Restore base PLY file from backup or reload base file into viewer."""
        base_path = self.pc.filename
        if not base_path:
            messagebox.showerror("Base File Not Found", "Base file is not specified.", parent=self)
            return

        bak_path = base_path + ".bak"
        has_bak = os.path.isfile(bak_path)

        msg = "Do you want to reload the base file '{}' into the viewer?".format(os.path.basename(base_path))
        if has_bak:
            msg += "\n\nNote: A backup file '{}' is available. Would you like to restore from this backup before reloading?".format(
                os.path.basename(bak_path)
            )

        confirm = messagebox.askyesno("Restore Base PLY", msg, parent=self)
        if not confirm:
            return

        try:
            base_file, was_restored = self.service.restore_base_ply()
            if self.on_reload_callback:
                self.on_reload_callback(base_file)

            self.refresh_advances()
            status_text = "restored from backup and loaded" if was_restored else "reloaded"
            messagebox.showinfo(
                "Base Restored",
                "Base file '{}' has been {} into viewer.".format(os.path.basename(base_file), status_text),
                parent=self
            )
        except Exception as e:
            messagebox.showerror("Restore Error", "Failed to restore base file: {}".format(e), parent=self)
