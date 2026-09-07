"""
ShortcutsTableView: Table listing point classes, label IDs and assigned key shortcuts.
"""
from tkinter import ttk

class ShortcutsTableView(ttk.Frame):
    """
    Treeview table for displaying and selecting class shortcuts.
    """
    COLUMNS = ("class_name", "label_id", "shortcut")

    def __init__(self, parent, on_double_click=None, **kwargs):
        super().__init__(parent, style='Modern.TFrame', **kwargs)
        self.on_double_click = on_double_click
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

        if self.on_double_click:
            self.tree.bind("<Double-1>", lambda e: self.on_double_click())

    def populate(self, class_items):
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
            self.tree.selection_set("0")
            self.tree.focus("0")

    def get_selected_item(self):
        """Return (class_name, label_id, key) for selected row."""
        sel = self.tree.selection()
        if not sel:
            return None
        idx = int(sel[0])
        if 0 <= idx < len(self.rows_data):
            return self.rows_data[idx]
        return None
