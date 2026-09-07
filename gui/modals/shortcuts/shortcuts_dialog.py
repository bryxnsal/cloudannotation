"""
ShortcutsDialog: Modal configuration window for editing, resetting, and disabling shortcuts.
Features tabbed interface for Classification shortcuts and Application Action shortcuts (All, Select, Open PLY, etc.)
with multi-key combinations (Ctrl+Z, Ctrl+Shift+S, etc.) and inline click+press reassignments.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import Config
from gui.theme import COLORS
from gui.modals.shortcuts.shortcuts_table_view import ShortcutsTableView
from gui.modals.shortcuts.shortcuts_capture_dialog import ShortcutsCaptureDialog
from gui.services.shortcut_manager import ACTION_DEFINITIONS, normalize_combo_string


class ShortcutsDialog(tk.Toplevel):
    """
    Dialog to customize, disable, reset and test point classification and action shortcuts.
    """
    def __init__(self, parent, shortcut_manager, on_applied_callback=None):
        super().__init__(parent)
        self.shortcut_manager = shortcut_manager
        self.on_applied_callback = on_applied_callback

        # Working copies
        self.working_classes = dict(shortcut_manager.key_to_class) # {combo: class_name}
        self.working_actions = dict(shortcut_manager.action_shortcuts) # {action_id: combo}
        self.enabled_var = tk.BooleanVar(self, value=shortcut_manager.enabled)

        self.title("Keyboard Shortcuts Configuration")
        self.geometry("680x560")
        self.minsize(600, 460)
        self.configure(bg=COLORS['bg_primary'])

        self._setup_ui()
        self.refresh_all_tables()

        self.transient(parent)
        self.update_idletasks()
        try:
            self.grab_set()
        except Exception:
            pass
        self.focus_force()

    def _setup_ui(self):
        # 1. Header Frame
        header_frame = ttk.Frame(self, style='Modern.TFrame')
        header_frame.pack(fill='x', padx=12, pady=(10, 6))

        title_lbl = ttk.Label(
            header_frame,
            text="Shortcuts & Key Combinations Configuration",
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
            text="Single-click a row & press any key/combo (e.g. Q, 1, Ctrl+Z, Ctrl+Shift+A) to assign, or 'Esc' to unassign.\nDouble-click opens capture popup. All shortcuts function directly inside 3D Viewers (PPTK / Open3D) and GUI.",
            style='Modern.TLabel',
            font=('Segoe UI', 9)
        )
        hint_lbl.pack(anchor='w', padx=12, pady=(0, 6))

        # 2. Notebook Tabs: [Point Classes] and [Application Actions]
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill='both', expand=True, padx=12, pady=4)

        # Tab 1: Point Classes
        tab_classes = ttk.Frame(self.notebook, style='Modern.TFrame')
        self.notebook.add(tab_classes, text=" Point Classes ")

        self.classes_table = ShortcutsTableView(
            tab_classes,
            col1_header="Class Name",
            col2_header="Label ID",
            on_double_click=self.assign_class_key_action,
            on_quick_key=self.quick_assign_class_key
        )
        self.classes_table.pack(fill='both', expand=True, padx=4, pady=4)

        # Tab 2: Application Actions (All, Select, Undo, Open PLY, etc.)
        tab_actions = ttk.Frame(self.notebook, style='Modern.TFrame')
        self.notebook.add(tab_actions, text=" Application Actions ")

        self.actions_table = ShortcutsTableView(
            tab_actions,
            col1_header="Action / Button",
            col2_header="Action ID",
            on_double_click=self.assign_action_key_action,
            on_quick_key=self.quick_assign_action_key
        )
        self.actions_table.pack(fill='both', expand=True, padx=4, pady=4)

        # 3. Middle Toolbar: Edit actions
        mid_bar = ttk.Frame(self, style='Modern.TFrame')
        mid_bar.pack(fill='x', padx=12, pady=(6, 4))

        ttk.Button(
            mid_bar,
            text="Assign Shortcut",
            style='Accent.TButton',
            command=self.on_assign_button_clicked
        ).pack(side='left', padx=(0, 4))

        ttk.Button(
            mid_bar,
            text="Clear Selected Shortcut",
            command=self.on_clear_button_clicked
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

    def refresh_all_tables(self, preserve_selection=True):
        """Refresh both Classes and Actions tables."""
        # Refresh Classes Table
        sel_class_idx = self.classes_table.get_selected_index() if preserve_selection else None
        class_to_key = {c: k for k, c in self.working_classes.items()}
        class_items = []
        for class_name, label_id in Config.labels.items():
            key = class_to_key.get(class_name, None)
            class_items.append((class_name, label_id, key))
        self.classes_table.populate(class_items, selected_index=sel_class_idx)

        # Refresh Actions Table
        sel_act_idx = self.actions_table.get_selected_index() if preserve_selection else None
        action_items = []
        for act_id, act_title, _ in ACTION_DEFINITIONS:
            key = self.working_actions.get(act_id, None)
            action_items.append((act_title, act_id, key))
        self.actions_table.populate(action_items, selected_index=sel_act_idx)

    # ------------------ Class Shortcuts Handling ------------------
    def quick_assign_class_key(self, combo):
        selected = self.classes_table.get_selected_item()
        if not selected:
            return
        class_name = selected[0]

        if combo == 'escape':
            for k in list(self.working_classes.keys()):
                if self.working_classes[k] == class_name:
                    del self.working_classes[k]
            self.refresh_all_tables(preserve_selection=True)
            return

        # Check conflict with actions
        for act_id, k in list(self.working_actions.items()):
            if k == combo:
                del self.working_actions[act_id]

        # Remove previous key for this class
        for k in list(self.working_classes.keys()):
            if self.working_classes[k] == class_name or k == combo:
                del self.working_classes[k]

        self.working_classes[combo] = class_name
        self.refresh_all_tables(preserve_selection=True)

    def assign_class_key_action(self):
        selected = self.classes_table.get_selected_item()
        if not selected:
            messagebox.showwarning("Selection Required", "Please select a class row first.", parent=self)
            return
        class_name, _, current_key = selected

        # Combined conflict mapping
        existing_mapping = dict(self.working_classes)
        for act_id, k in self.working_actions.items():
            if k:
                existing_mapping[k] = "Action: " + act_id

        dlg = ShortcutsCaptureDialog(self, class_name, current_key, existing_mapping, item_type="Class")
        self.wait_window(dlg)

        if dlg.result_key is not None:
            new_key = dlg.result_key
            for k in list(self.working_classes.keys()):
                if self.working_classes[k] == class_name:
                    del self.working_classes[k]
            if new_key:
                # Remove if assigned to action
                for act_id, k in list(self.working_actions.items()):
                    if k == new_key:
                        del self.working_actions[act_id]
                self.working_classes[new_key] = class_name
            self.refresh_all_tables(preserve_selection=True)

    # ------------------ Action Shortcuts Handling ------------------
    def quick_assign_action_key(self, combo):
        selected = self.actions_table.get_selected_item()
        if not selected:
            return
        action_id = selected[1]

        if combo == 'escape':
            self.working_actions[action_id] = None
            self.refresh_all_tables(preserve_selection=True)
            return

        # Remove from other actions
        for a_id, k in list(self.working_actions.items()):
            if k == combo:
                self.working_actions[a_id] = None

        # Remove from classes
        for k in list(self.working_classes.keys()):
            if k == combo:
                del self.working_classes[k]

        self.working_actions[action_id] = combo
        self.refresh_all_tables(preserve_selection=True)

    def assign_action_key_action(self):
        selected = self.actions_table.get_selected_item()
        if not selected:
            messagebox.showwarning("Selection Required", "Please select an action row first.", parent=self)
            return
        action_title, action_id, current_key = selected

        # Combined conflict mapping
        existing_mapping = dict(self.working_classes)
        for a_id, k in self.working_actions.items():
            if k:
                existing_mapping[k] = "Action: " + a_id

        dlg = ShortcutsCaptureDialog(self, action_title, current_key, existing_mapping, item_type="Action")
        self.wait_window(dlg)

        if dlg.result_key is not None:
            new_key = dlg.result_key
            if not new_key:
                self.working_actions[action_id] = None
            else:
                # Remove from other actions or classes
                for a_id, k in list(self.working_actions.items()):
                    if k == new_key:
                        self.working_actions[a_id] = None
                for k in list(self.working_classes.keys()):
                    if k == new_key:
                        del self.working_classes[k]
                self.working_actions[action_id] = new_key
            self.refresh_all_tables(preserve_selection=True)

    # ------------------ Toolbar Button Handlers ------------------
    def on_assign_button_clicked(self):
        active_tab = self.notebook.index(self.notebook.select())
        if active_tab == 0:
            self.assign_class_key_action()
        else:
            self.assign_action_key_action()

    def on_clear_button_clicked(self):
        active_tab = self.notebook.index(self.notebook.select())
        if active_tab == 0:
            selected = self.classes_table.get_selected_item()
            if selected:
                class_name = selected[0]
                for k in list(self.working_classes.keys()):
                    if self.working_classes[k] == class_name:
                        del self.working_classes[k]
        else:
            selected = self.actions_table.get_selected_item()
            if selected:
                action_id = selected[1]
                self.working_actions[action_id] = None
        self.refresh_all_tables(preserve_selection=True)

    def disable_all_shortcuts_action(self):
        confirm = messagebox.askyesno(
            "Disable All Shortcuts",
            "Are you sure you want to disable all shortcuts?\n"
            "You can always restore them with 'Reset Defaults'.",
            parent=self
        )
        if confirm:
            self.working_classes.clear()
            for k in self.working_actions:
                self.working_actions[k] = None
            self.enabled_var.set(False)
            self.refresh_all_tables()

    def reset_defaults_action(self):
        confirm = messagebox.askyesno(
            "Reset Defaults",
            "Reset all classification shortcuts to default layout (1-9, 0, Q-O) and actions?",
            parent=self
        )
        if confirm:
            self.working_classes = self.shortcut_manager.get_default_classification_mapping()
            self.working_actions = self.shortcut_manager.get_default_action_shortcuts()
            self.enabled_var.set(True)
            self.refresh_all_tables()

    def save_and_apply_action(self):
        is_enabled = self.enabled_var.get()
        self.shortcut_manager.set_mapping(
            new_key_to_class=self.working_classes,
            new_action_shortcuts=self.working_actions,
            enabled=is_enabled
        )
        if self.on_applied_callback:
            self.on_applied_callback()

        messagebox.showinfo(
            "Shortcuts Applied",
            "All shortcuts have been saved and applied successfully.",
            parent=self
        )
        self.destroy()
