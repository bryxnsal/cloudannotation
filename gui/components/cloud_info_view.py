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

        # Row 1: Points and Point Size (Slider + Textbox)
        ttk.Label(grid_frame, text="Points:", style='Title.TLabel', font=('Segoe UI', 9, 'bold')).grid(row=1, column=0, sticky='w', padx=(0, 4), pady=(2, 0))
        self.info_points_lbl = ttk.Label(grid_frame, text="-", style='Modern.TLabel', font=('Segoe UI', 9))
        self.info_points_lbl.grid(row=1, column=1, sticky='w', padx=(0, 10), pady=(2, 0))

        ttk.Label(grid_frame, text="Pt Size:", style='Title.TLabel', font=('Segoe UI', 9, 'bold')).grid(row=1, column=2, sticky='w', padx=(0, 4), pady=(2, 0))
        
        # Container for Slider + Entry
        ptsize_frame = ttk.Frame(grid_frame, style='Modern.TFrame')
        ptsize_frame.grid(row=1, column=3, sticky='ew', pady=(2, 0))

        self.ptsize_var = ttk.tkinter.StringVar(value="0.010")
        self._updating_ptsize = False

        self.ptsize_slider = ttk.Scale(
            ptsize_frame,
            from_=0.001,
            to=0.080,
            orient='horizontal',
            command=self._on_slider_change
        )
        self.ptsize_slider.set(0.010)
        self.ptsize_slider.pack(side='left', fill='x', expand=True, padx=(0, 4))

        self.ptsize_entry = ttk.Entry(
            ptsize_frame,
            textvariable=self.ptsize_var,
            width=6,
            font=('Segoe UI', 8)
        )
        self.ptsize_entry.pack(side='right')
        self.ptsize_entry.bind('<Return>', lambda e: self._on_entry_submit())
        self.ptsize_entry.bind('<FocusOut>', lambda e: self._on_entry_submit())

        # Row 2: Date and Modified
        ttk.Label(grid_frame, text="Date:", style='Title.TLabel', font=('Segoe UI', 9, 'bold')).grid(row=2, column=0, sticky='w', padx=(0, 4), pady=(2, 0))
        self.info_date_lbl = ttk.Label(grid_frame, text="-", style='Modern.TLabel', font=('Segoe UI', 9))
        self.info_date_lbl.grid(row=2, column=1, sticky='w', padx=(0, 10), pady=(2, 0))

        ttk.Label(grid_frame, text="Modified:", style='Title.TLabel', font=('Segoe UI', 9, 'bold')).grid(row=2, column=2, sticky='w', padx=(0, 4), pady=(2, 0))
        self.info_modified_lbl = ttk.Label(grid_frame, text="-", style='Modern.TLabel', font=('Segoe UI', 9))
        self.info_modified_lbl.grid(row=2, column=3, sticky='w', pady=(2, 0))

    def _on_slider_change(self, val):
        """Called when slider moves."""
        if self._updating_ptsize:
            return
        try:
            val_float = float(val)
            self._updating_ptsize = True
            self.ptsize_var.set("{:.3f}".format(val_float))
            self._updating_ptsize = False
            if self.pc:
                self.pc.set_point_size(val_float)
        except Exception:
            pass

    def _on_entry_submit(self):
        """Called when entry text is edited and submitted."""
        if self._updating_ptsize:
            return
        raw = self.ptsize_var.get().strip()
        try:
            val_float = float(raw)
            if val_float > 0:
                self._updating_ptsize = True
                self.ptsize_slider.set(val_float)
                self.ptsize_var.set("{:.3f}".format(val_float))
                self._updating_ptsize = False
                if self.pc:
                    self.pc.set_point_size(val_float)
        except ValueError:
            # Restore previous slider value
            self.ptsize_var.set("{:.3f}".format(self.ptsize_slider.get()))

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

            pt_size = stats.get('point_size', None)
            if pt_size is not None and not self._updating_ptsize:
                self._updating_ptsize = True
                try:
                    pt_size_val = float(pt_size)
                    self.ptsize_slider.set(pt_size_val)
                    self.ptsize_var.set("{:.3f}".format(pt_size_val))
                except Exception:
                    pass
                self._updating_ptsize = False

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
