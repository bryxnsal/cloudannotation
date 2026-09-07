"""
ShortcutsTableView: Table listing point classes or actions, identifiers and assigned key shortcuts.
Supports single-click focus, double-click modal assignment, and quick inline keypress assignment.
"""
from tkinter import ttk
from gui.modals.shortcuts.shortcuts_capture_dialog import event_to_combo

class ShortcutsTableView(ttk.Frame):
    """
    Treeview table for displaying and selecting shortcuts.
    """
    COLUMNS = ("item_name", "item_id", "shortcut")

    def __init__(self, parent, col1_header="Class Name", col2_header="Label ID",
                 on_double_click=None, on_quick_key=None, **kwargs):
        super().__init__(parent, style='Modern.TFrame', **kwargs)
        self.col1_header = col1_header
        self.col2_header = col2_header
        self.on_double_click = on_double_click
        self.on_quick_key = on_quick_key
        self.rows_data = []

        self._create_widgets()

    def _create_widgets(self):
        # Scrollbar
        scroll = ttk.Scrollbar(self, orient='vertical')
        scroll.pack(side='right', fill='y')

        self.tree = ttk.Treeview(
            self,
            columns=self.COLUMNS,
            show='headings',
            selectmode='browse',
            yscrollcommand=scroll.set
        )

        self.tree.heading("item_name", text=self.col1_header)
        self.tree.heading("item_id", text=self.col2_header)
        self.tree.heading("shortcut", text="Assigned Shortcut")

        self.tree.column("item_name", width=220, anchor='w')
        self.tree.column("item_id", width=90, anchor='center')
        self.tree.column("shortcut", width=170, anchor='center')

        self.tree.pack(fill='both', expand=True)
        scroll.config(command=self.tree.yview)

        # Ensure single click gives keyboard focus to the tree
        def _on_single_click(e):
            item = self.tree.identify_row(e.y)
            if item:
                self.tree.selection_set(item)
                self.tree.focus(item)

        self.tree.bind("<Button-1>", _on_single_click)

        if self.on_double_click:
            def _on_dbl(e):
                item = self.tree.identify_row(e.y)
                if item:
                    self.tree.selection_set(item)
                    self.tree.focus(item)
                self.on_double_click()
            self.tree.bind("<Double-1>", _on_dbl)

        if self.on_quick_key:
            def _on_tree_key(event):
                # Standard navigation
                if event.keysym in ('Up', 'Down', 'Prior', 'Next', 'Home', 'End'):
                    return

                # Escape alone clears the shortcut
                if event.keysym == 'Escape' and not (event.state & 0x4 or event.state & 0x1 or event.state & 0x8):
                    self.on_quick_key('escape')
                    return "break"

                combo = event_to_combo(event)
                if combo:
                    self.on_quick_key(combo)
                    return "break"

            self.tree.bind("<Key>", _on_tree_key)

    def populate(self, items, selected_index=None):
        """
        Populate table with list of tuples: (item_name, item_id, assigned_shortcut)
        """
        for item in self.tree.get_children():
            self.tree.delete(item)

        self.rows_data = list(items)

        for idx, (name, i_id, key) in enumerate(self.rows_data):
            key_display = "[ {} ]".format(key.upper()) if key else "- None -"
            self.tree.insert(
                "",
                "end",
                iid=str(idx),
                values=(name, i_id, key_display)
            )

        if self.rows_data:
            target_idx = "0"
            if selected_index is not None and 0 <= int(selected_index) < len(self.rows_data):
                target_idx = str(selected_index)
            self.tree.selection_set(target_idx)
            self.tree.focus(target_idx)
            self.tree.see(target_idx)

    def get_selected_index(self):
        """Return integer index of the currently selected row, or None."""
        sel = self.tree.selection()
        if not sel:
            return None
        try:
            return int(sel[0])
        except (ValueError, TypeError):
            return None

    def get_selected_item(self):
        """Return (item_name, item_id, key) for selected row."""
        sel = self.tree.selection()
        if not sel:
            return None
        idx = int(sel[0])
        if 0 <= idx < len(self.rows_data):
            return self.rows_data[idx]
        return None
