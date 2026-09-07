"""
ShortcutsDialog: Modal configuration window for editing, resetting, and disabling shortcuts.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import Config
from gui.theme import COLORS
from gui.modals.shortcuts.shortcuts_table_view import ShortcutsTableView
from gui.modals.shortcuts.shortcuts_capture_dialog import ShortcutsCaptureDialog

class ShortcutsDialog(tk.Toplevel):
    """
    Dialog to customize, disable, reset and test point classification shortcuts.
    """
    def __init__(self, parent, shortcut_manager, on_applied_callback=None):
        super().__init__(parent)
        self.shortcut_manager = shortcut_manager
        self.on_applied_callback = on_applied_callback

        # In-memory working copy
        self.working_mapping = dict(shortcut_manager.key_to_class) # {key: class_name}
        self.enabled_var = tk.BooleanVar(self, value=shortcut_manager.enabled)

        self.title("Keyboard Shortcuts - Point Cloud Classification")
        self.geometry("620x520")
        self.minsize(560, 420)
        self.configure(bg=COLORS['bg_primary'])

        self.transient(parent)
        self.grab_set()

        self._setup_ui()
        self.refresh_table()

    def _setup_ui(self):
        # 1. Header Frame
        header_frame = ttk.Frame(self, style='Modern.TFrame')
        header_frame.pack(fill='x', padx=12, pady=(10, 6))

        title_lbl = ttk.Label(
            header_frame,
            text="Classification Shortcuts Configuration",
            style='Title.TLabel',
            font=('Segoe UI', 11, 'bold')
        )
        title_lbl.pack(side='left')

        # Global Enable/Disable Checkbox
        self.enable_chk = ttk.Checkbutton(
            header_frame,
            text="Enable Shortcuts",
            variable=self.enabled_var,
            style='Modern.TCheckbutton'
        )
        self.enable_chk.pack(side='right')

        # Subtitle hint
        hint_lbl = ttk.Label(
            self,
            text="Double-click a row or click 'Assign Key'. Shortcuts work directly in 3D viewers and GUI.\nNote: In PPTK, keys 1-9 rotate camera if no points are selected, or classify points if selected.",
            style='Modern.TLabel',
            font=('Segoe UI', 9)
        )
        hint_lbl.pack(anchor='w', padx=12, pady=(0, 6))

        # 2. Table
        table_container = ttk.Frame(self, style='Modern.TFrame')
        table_container.pack(fill='both', expand=True, padx=12, pady=4)

        self.table_view = ShortcutsTableView(
            table_container,
            on_double_click=self.assign_key_action
        )
        self.table_view.pack(fill='both', expand=True)

        # 3. Middle Toolbar: Edit actions
        mid_bar = ttk.Frame(self, style='Modern.TFrame')
        mid_bar.pack(fill='x', padx=12, pady=(6, 4))

        ttk.Button(
            mid_bar,
            text="Assign Key",
            style='Accent.TButton',
            command=self.assign_key_action
        ).pack(side='left', padx=(0, 4))

        ttk.Button(
            mid_bar,
            text="Clear Selected Key",
            command=self.clear_key_action
        ).pack(side='left', padx=(0, 4))

        ttk.Button(
            mid_bar,
            text="Disable All Shortcuts",
            command=self.disable_all_shortcuts_action
        ).pack(side='left', padx=(0, 4))

        ttk.Button(
            mid_bar,
            text="Reset Defaults",
            command=self.reset_defaults_action
        ).pack(side='right')

        # 4. Bottom action bar: Save & Cancel
        bottom_bar = ttk.Frame(self, style='Modern.TFrame')
        bottom_bar.pack(fill='x', padx=12, pady=(8, 12))

        ttk.Button(
            bottom_bar,
            text="Save & Apply",
            style='Accent.TButton',
            command=self.save_and_apply_action
        ).pack(side='left', padx=(0, 6))

        ttk.Button(
            bottom_bar,
            text="Cancel",
            command=self.destroy
        ).pack(side='right')

    def refresh_table(self, preserve_selection=True):
        """Build items list from Config.labels and current working_mapping."""
        selected_idx = self.table_view.get_selected_index() if preserve_selection else None
        class_to_key = {c: k for k, c in self.working_mapping.items()}
        items = []
        for class_name, label_id in Config.labels.items():
            key = class_to_key.get(class_name, None)
            items.append((class_name, label_id, key))
        self.table_view.populate(items, selected_index=selected_idx)

    def assign_key_action(self):
        """Open capture popup to assign new key to selected row."""
        selected = self.table_view.get_selected_item()
        if not selected:
            messagebox.showwarning("Selection Required", "Please select a class from the list first.", parent=self)
            return

        class_name, _, current_key = selected
        dlg = ShortcutsCaptureDialog(self, class_name, current_key, self.working_mapping)
        self.wait_window(dlg)

        if dlg.result_key is not None:
            new_key = dlg.result_key
            # Remove previous key for this class
            for k in list(self.working_mapping.keys()):
                if self.working_mapping[k] == class_name:
                    del self.working_mapping[k]

            if new_key:  # Not empty string
                # If key was assigned to another class, remove it first
                if new_key in self.working_mapping:
                    del self.working_mapping[new_key]
                self.working_mapping[new_key] = class_name

            self.refresh_table(preserve_selection=True)

    def clear_key_action(self):
        """Clear key assigned to selected class."""
        selected = self.table_view.get_selected_item()
        if not selected:
            return
        class_name = selected[0]
        for k in list(self.working_mapping.keys()):
            if self.working_mapping[k] == class_name:
                del self.working_mapping[k]
        self.refresh_table(preserve_selection=True)

    def disable_all_shortcuts_action(self):
        """Clear all shortcuts and uncheck Enable checkbox."""
        confirm = messagebox.askyesno(
            "Disable All Shortcuts",
            "Are you sure you want to disable and clear all key shortcuts?\n"
            "You can always restore them with 'Reset Defaults'.",
            parent=self
        )
        if confirm:
            self.working_mapping.clear()
            self.enabled_var.set(False)
            self.refresh_table()

    def reset_defaults_action(self):
        """Reset working mapping to factory defaults."""
        confirm = messagebox.askyesno(
            "Reset Defaults",
            "Reset all shortcuts to default layout (1-9, 0, and Q-O)?",
            parent=self
        )
        if confirm:
            self.working_mapping = self.shortcut_manager.get_default_mapping()
            self.enabled_var.set(True)
            self.refresh_table()

    def save_and_apply_action(self):
        """Save to file and notify app to re-bind."""
        is_enabled = self.enabled_var.get()
        self.shortcut_manager.set_mapping(self.working_mapping, enabled=is_enabled)
        if self.on_applied_callback:
            self.on_applied_callback()

        messagebox.showinfo(
            "Shortcuts Applied",
            "Shortcuts have been saved and applied successfully.",
            parent=self
        )
        self.destroy()
