"""
ShortcutsTableView: Table listing point classes, label IDs and assigned key shortcuts.
"""
from tkinter import ttk

class ShortcutsTableView(ttk.Frame):
    """
    Treeview table for displaying and selecting class shortcuts.
    """
    COLUMNS = ("class_name", "label_id", "shortcut")

    def __init__(self, parent, on_double_click=None, on_quick_key=None, **kwargs):
        super().__init__(parent, style='Modern.TFrame', **kwargs)
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

        self.tree.heading("class_name", text="Class Name")
        self.tree.heading("label_id", text="Label ID")
        self.tree.heading("shortcut", text="Assigned Key Shortcut")

        self.tree.column("class_name", width=220, anchor='w')
        self.tree.column("label_id", width=90, anchor='center')
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
                # If Up/Down/Prior/Next, let standard navigation happen
                if event.keysym in ('Up', 'Down', 'Left', 'Right', 'Prior', 'Next', 'Home', 'End'):
                    return
                # If Escape
                if event.keysym == 'Escape':
                    self.on_quick_key('escape')
                    return "break"
                # If alphanumeric or keypad
                char = event.char
                if not char:
                    if event.keysym.startswith('KP_') and len(event.keysym) == 4 and event.keysym[3].isdigit():
                        char = event.keysym[3]
                if char and char.isalnum() and len(char) == 1:
                    self.on_quick_key(char.lower())
                    return "break"
            self.tree.bind("<Key>", _on_tree_key)

    def populate(self, class_items, selected_index=None):
        """
        Populate table with list of tuples: (class_name, label_id, assigned_key)
        """
        for item in self.tree.get_children():
            self.tree.delete(item)

        self.rows_data = list(class_items)

        for idx, (c_name, l_id, key) in enumerate(self.rows_data):
            key_display = "[ {} ]".format(key.upper()) if key else "- None -"
            self.tree.insert(
                "",
                "end",
                iid=str(idx),
                values=(c_name, l_id, key_display)
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
        """Return (class_name, label_id, key) for selected row."""
        sel = self.tree.selection()
        if not sel:
            return None
        idx = int(sel[0])
        if 0 <= idx < len(self.rows_data):
            return self.rows_data[idx]
        return None
