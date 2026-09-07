"""
AdvancesTableView: Presentation component for advances list using ttk.Treeview.
Decoupled view with column headers, scrolling and double-click event handling.
"""
import tkinter as tk
from tkinter import ttk

class AdvancesTableView(ttk.Frame):
    """
    Treeview table for listing and selecting point cloud advances.
    """
    COLUMNS = ("filename", "date", "size", "points", "changed_pts", "changed_ratio")

    def __init__(self, parent, on_double_click=None, **kwargs):
        super().__init__(parent, style='Modern.TFrame', **kwargs)
        self.on_double_click = on_double_click
        self.advances_data = []

        self._create_widgets()

    def _create_widgets(self):
        # Scrollbars
        y_scroll = ttk.Scrollbar(self, orient='vertical')
        y_scroll.pack(side='right', fill='y')

        x_scroll = ttk.Scrollbar(self, orient='horizontal')
        x_scroll.pack(side='bottom', fill='x')

        # Treeview
        self.tree = ttk.Treeview(
            self,
            columns=self.COLUMNS,
            show='headings',
            selectmode='browse',
            yscrollcommand=y_scroll.set,
            xscrollcommand=x_scroll.set
        )

        self.tree.heading("filename", text="Advance File")
        self.tree.heading("date", text="Date & Time")
        self.tree.heading("size", text="Size")
        self.tree.heading("points", text="Points")
        self.tree.heading("changed_pts", text="Modified Points")
        self.tree.heading("changed_ratio", text="% Changed vs Base")

        self.tree.column("filename", width=240, anchor='w')
        self.tree.column("date", width=140, anchor='center')
        self.tree.column("size", width=80, anchor='center')
        self.tree.column("points", width=90, anchor='center')
        self.tree.column("changed_pts", width=130, anchor='center')
        self.tree.column("changed_ratio", width=140, anchor='center')

        self.tree.pack(fill='both', expand=True)
        y_scroll.config(command=self.tree.yview)
        x_scroll.config(command=self.tree.xview)

        if self.on_double_click:
            self.tree.bind("<Double-1>", lambda e: self.on_double_click())

    def populate(self, advances_list):
        """
        Clear table and populate with advances items.
        """
        for item in self.tree.get_children():
            self.tree.delete(item)

        self.advances_data = list(advances_list)

        for idx, adv in enumerate(self.advances_data):
            self.tree.insert(
                "",
                "end",
                iid=str(idx),
                values=(
                    adv['filename'],
                    adv['mtime'],
                    adv['size_mb'],
                    "{:,}".format(adv['total_pts']),
                    "{:,}".format(adv['changed_pts']),
                    adv['changed_ratio_str']
                )
            )

        if self.advances_data:
            self.tree.selection_set("0")
            self.tree.focus("0")

    def get_selected_advance(self):
        """
        Return dictionary info of currently selected advance or None.
        """
        selected = self.tree.selection()
        if not selected:
            return None
        idx = int(selected[0])
        if 0 <= idx < len(self.advances_data):
            return self.advances_data[idx]
        return None
