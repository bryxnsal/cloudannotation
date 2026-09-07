"""
CloudInfoView: Presentation component for [INFO] section.
Displays PLY point cloud metadata: filename, size, points, point size, date, modified points vs base.
"""
from tkinter import ttk
from gui.components.base_component import BaseComponent

class CloudInfoView(BaseComponent):
    """
    Shows read-only metadata about the currently loaded point cloud.
    """
    def __init__(self, parent, app, pc, **kwargs):
        super().__init__(parent, app, pc, **kwargs)
        self._create_widgets()

    def _create_widgets(self):
        section_frame = ttk.LabelFrame(
            self,
            text=" [INFO] ",
            style='Modern.TLabelframe',
            padding=8
        )
        section_frame.pack(fill='x')

        grid_frame = ttk.Frame(section_frame, style='Modern.TFrame')
        grid_frame.pack(fill='x')
        grid_frame.columnconfigure(1, weight=1)
        grid_frame.columnconfigure(3, weight=1)

        # Row 0: File and Size
        ttk.Label(grid_frame, text="File:", style='Title.TLabel', font=('Segoe UI', 9, 'bold')).grid(row=0, column=0, sticky='w', padx=(0, 4))
        self.info_file_lbl = ttk.Label(grid_frame, text="-", style='Modern.TLabel', font=('Segoe UI', 9))
        self.info_file_lbl.grid(row=0, column=1, sticky='w', padx=(0, 10))

        ttk.Label(grid_frame, text="Size:", style='Title.TLabel', font=('Segoe UI', 9, 'bold')).grid(row=0, column=2, sticky='w', padx=(0, 4))
        self.info_size_lbl = ttk.Label(grid_frame, text="-", style='Modern.TLabel', font=('Segoe UI', 9))
        self.info_size_lbl.grid(row=0, column=3, sticky='w')

        # Row 1: Points and Point Size
        ttk.Label(grid_frame, text="Points:", style='Title.TLabel', font=('Segoe UI', 9, 'bold')).grid(row=1, column=0, sticky='w', padx=(0, 4), pady=(2, 0))
        self.info_points_lbl = ttk.Label(grid_frame, text="-", style='Modern.TLabel', font=('Segoe UI', 9))
        self.info_points_lbl.grid(row=1, column=1, sticky='w', padx=(0, 10), pady=(2, 0))

        ttk.Label(grid_frame, text="Pt Size:", style='Title.TLabel', font=('Segoe UI', 9, 'bold')).grid(row=1, column=2, sticky='w', padx=(0, 4), pady=(2, 0))
        self.info_ptsize_lbl = ttk.Label(grid_frame, text="-", style='Modern.TLabel', font=('Segoe UI', 9))
        self.info_ptsize_lbl.grid(row=1, column=3, sticky='w', pady=(2, 0))

        # Row 2: Date and Modified
        ttk.Label(grid_frame, text="Date:", style='Title.TLabel', font=('Segoe UI', 9, 'bold')).grid(row=2, column=0, sticky='w', padx=(0, 4), pady=(2, 0))
        self.info_date_lbl = ttk.Label(grid_frame, text="-", style='Modern.TLabel', font=('Segoe UI', 9))
        self.info_date_lbl.grid(row=2, column=1, sticky='w', padx=(0, 10), pady=(2, 0))

        ttk.Label(grid_frame, text="Modified:", style='Title.TLabel', font=('Segoe UI', 9, 'bold')).grid(row=2, column=2, sticky='w', padx=(0, 4), pady=(2, 0))
        self.info_modified_lbl = ttk.Label(grid_frame, text="-", style='Modern.TLabel', font=('Segoe UI', 9))
        self.info_modified_lbl.grid(row=2, column=3, sticky='w', pady=(2, 0))

    def update_stats(self, stats):
        """
        Update label texts from given stats dictionary.
        """
        try:
            fname = stats.get('filename', 'Unknown')
            if len(fname) > 22:
                fname = fname[:10] + "..." + fname[-9:]
            self.info_file_lbl.configure(text=fname)

            self.info_size_lbl.configure(text="{:.1f} MB".format(stats.get('file_size_mb', 0.0)))
            self.info_points_lbl.configure(text="{:,}".format(stats.get('total_points', 0)))
            self.info_ptsize_lbl.configure(text="{}".format(stats.get('point_size', '-')))

            mtime = stats.get('mtime')
            if mtime:
                self.info_date_lbl.configure(text=mtime.strftime("%Y-%m-%d %H:%M"))
            else:
                self.info_date_lbl.configure(text="N/A")

            changed_pts = stats.get('changed_points', 0)
            changed_ratio = stats.get('changed_ratio', 0.0)
            if changed_pts > 0:
                self.info_modified_lbl.configure(text="{:,} ({:.2f}%)".format(changed_pts, changed_ratio))
            else:
                self.info_modified_lbl.configure(text="0 (0.0%)")
        except Exception as e:
            print("Error updating CloudInfoView labels:", e)
