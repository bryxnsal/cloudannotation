import os
import shutil
import datetime
import tkinter as tk
from tkinter import ttk, messagebox
from plyfile import PlyData
import numpy as np


class AdvancesModal(tk.Toplevel):
    """
    Modal window to inspect, compare, load, overwrite and restore advances.
    """

    def __init__(self, parent, pc, on_reload_callback=None):
        super().__init__(parent)
        self.pc = pc
        self.on_reload_callback = on_reload_callback

        self.title("Advances Management - Point Cloud")
        self.geometry("860x500")
        self.minsize(750, 400)
        self.configure(bg='#2b2b2b')

        # Make modal
        self.transient(parent)
        self.grab_set()

        self.colors = {
            'bg_primary': '#2b2b2b',
            'bg_secondary': '#3c3c3c',
            'bg_accent': '#4a4a4a',
            'text_primary': '#ffffff',
            'text_secondary': '#cccccc',
            'accent': '#007acc',
            'success': '#4caf50',
            'warning': '#ff9800',
            'error': '#f44336',
            'border': '#555555'
        }

        self.base_classes = None
        self.advances_data = []

        self._setup_ui()
        self._load_advances()

    def _setup_ui(self):
        # Header frame
        header_frame = ttk.Frame(self, style='Modern.TFrame')
        header_frame.pack(fill='x', padx=12, pady=(10, 6))

        base_name = os.path.basename(self.pc.filename) if self.pc.filename else "Unknown"
        title_lbl = ttk.Label(
            header_frame, 
            text=f"Advances History for: {base_name}",
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

        # Table frame (Treeview)
        table_frame = ttk.Frame(self, style='Modern.TFrame')
        table_frame.pack(fill='both', expand=True, padx=12, pady=4)

        # Scrollbars
        y_scroll = ttk.Scrollbar(table_frame, orient='vertical')
        y_scroll.pack(side='right', fill='y')

        x_scroll = ttk.Scrollbar(table_frame, orient='horizontal')
        x_scroll.pack(side='bottom', fill='x')

        columns = ("filename", "date", "size", "points", "changed_pts", "changed_ratio")
        self.tree = ttk.Treeview(
            table_frame,
            columns=columns,
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

        # Style treeview
        style = ttk.Style()
        style.configure(
            "Treeview",
            background="#333333",
            foreground="#ffffff",
            fieldbackground="#333333",
            rowheight=24,
            font=('Segoe UI', 9)
        )
        style.configure(
            "Treeview.Heading",
            background="#444444",
            foreground="#ffffff",
            font=('Segoe UI', 9, 'bold')
        )
        style.map(
            "Treeview",
            background=[('selected', self.colors['accent'])],
            foreground=[('selected', '#ffffff')]
        )

        # Double click to load advance
        self.tree.bind("<Double-1>", lambda e: self.load_advance_in_viewer())

        # Buttons Frame
        btn_frame = ttk.Frame(self, style='Modern.TFrame')
        btn_frame.pack(fill='x', padx=12, pady=(8, 12))

        # Left action buttons
        self.load_btn = ttk.Button(
            btn_frame, 
            text="Load Advance in Viewer", 
            style='Accent.TButton',
            command=self.load_advance_in_viewer
        )
        self.load_btn.pack(side='left', padx=(0, 6))

        self.overwrite_btn = ttk.Button(
            btn_frame, 
            text="Overwrite Base PLY", 
            command=self.overwrite_base_ply
        )
        self.overwrite_btn.pack(side='left', padx=(0, 6))

        self.restore_btn = ttk.Button(
            btn_frame, 
            text="Restore Base PLY", 
            command=self.restore_base_ply
        )
        self.restore_btn.pack(side='left', padx=(0, 6))

        # Refresh and Close on right
        ttk.Button(
            btn_frame, 
            text="Close", 
            command=self.destroy
        ).pack(side='right', padx=(6, 0))

        ttk.Button(
            btn_frame, 
            text="Refresh", 
            command=self._load_advances
        ).pack(side='right')

    def _get_base_classes(self):
        """Get the base point classes array for comparison."""
        if hasattr(self.pc, 'base_classes') and self.pc.base_classes is not None:
            return self.pc.base_classes

        base_path = self.pc.filename
        if base_path and os.path.isfile(base_path):
            try:
                p = PlyData.read(base_path)
                if 'class' in p['vertex'].data.dtype.names:
                    return p['vertex'].data['class']
            except Exception as e:
                print(f"Error reading base file {base_path}: {e}")
        return None

    def _get_file_info(self, filepath, base_classes=None):
        """Quickly read ply element stats and compare point-by-point with base file."""
        try:
            stat = os.stat(filepath)
            mtime = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            size_mb = f"{stat.st_size / (1024 * 1024):.1f} MB"

            plydata = PlyData.read(filepath)
            v_data = plydata['vertex'].data
            total_pts = len(v_data)

            changed_pts = 0
            changed_ratio_str = "0.0%"
            if 'class' in v_data.dtype.names and base_classes is not None and len(base_classes) == total_pts:
                cls_arr = v_data['class']
                changed_pts = int((cls_arr != base_classes).sum())
                if total_pts > 0:
                    changed_ratio_str = f"{(changed_pts / total_pts * 100.0):.2f}%"

            return {
                'filepath': filepath,
                'filename': os.path.basename(filepath),
                'mtime': mtime,
                'size_mb': size_mb,
                'total_pts': total_pts,
                'changed_pts': changed_pts,
                'changed_ratio_str': changed_ratio_str,
                'raw_mtime': stat.st_mtime
            }
        except Exception as e:
            print(f"Error reading file {filepath}: {e}")
            return None

    def _load_advances(self):
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.advances_data.clear()

        # Compute base classes
        self.base_classes = self._get_base_classes()

        advances_dir = self.pc.get_advances_dir()
        if not advances_dir or not os.path.isdir(advances_dir):
            self.summary_lbl.config(text="No advances folder found.")
            return

        # Find all ply files in advances
        ply_files = [
            os.path.join(advances_dir, f)
            for f in os.listdir(advances_dir)
            if f.lower().endswith('.ply')
        ]

        # Sort newest first
        advances_list = []
        for pf in ply_files:
            info = self._get_file_info(pf, self.base_classes)
            if info:
                advances_list.append(info)

        advances_list.sort(key=lambda x: x['raw_mtime'], reverse=True)
        self.advances_data = advances_list

        for idx, item in enumerate(advances_list):
            diff_display = f"{item['changed_pts']:,} pts" if item['changed_pts'] > 0 else "None (identical)"

            self.tree.insert(
                "",
                "end",
                iid=str(idx),
                values=(
                    item['filename'],
                    item['mtime'],
                    item['size_mb'],
                    f"{item['total_pts']:,}",
                    diff_display,
                    item['changed_ratio_str']
                )
            )

        count = len(advances_list)
        self.summary_lbl.config(text=f"Total Advances: {count}")
        if count > 0:
            self.tree.selection_set("0")

    def _get_selected_advance(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Please select an advance from the list.", parent=self)
            return None
        idx = int(sel[0])
        return self.advances_data[idx]

    def load_advance_in_viewer(self):
        """Load selected advance into PointCloud in-memory points and refresh viewer."""
        advance = self._get_selected_advance()
        if not advance:
            return

        filepath = advance['filepath']
        try:
            # Reload cloud in memory (retaining current base_classes for comparison)
            self.pc.reload_from_file(filepath, preserve_camera=True, is_new_base=False)

            if self.on_reload_callback:
                self.on_reload_callback(filepath)

            messagebox.showinfo(
                "Advance Loaded",
                f"Successfully loaded '{advance['filename']}' into viewer.\n"
                "You can now continue labeling and use 'Save Advance' to save further progress.",
                parent=self
            )
        except Exception as e:
            messagebox.showerror("Error Loading Advance", f"Failed to load advance: {str(e)}", parent=self)

    def overwrite_base_ply(self):
        """Overwrite base PLY file with the selected advance."""
        advance = self._get_selected_advance()
        if not advance:
            return

        base_path = self.pc.filename
        if not base_path or not os.path.isfile(base_path):
            messagebox.showerror("Base File Not Found", "Could not locate the base PLY file.", parent=self)
            return

        confirm = messagebox.askyesno(
            "Confirm Overwrite",
            f"Are you sure you want to overwrite the base file:\n'{os.path.basename(base_path)}'\n\n"
            f"with advance:\n'{advance['filename']}'?\n\n"
            "A safety backup (.bak) of the current base file will be created automatically.",
            parent=self
        )
        if not confirm:
            return

        try:
            # 1. Create backup of current base file
            bak_path = base_path + ".bak"
            shutil.copy2(base_path, bak_path)

            # 2. Overwrite base file with advance
            shutil.copy2(advance['filepath'], base_path)

            # 3. Reload base file into memory as new base
            self.pc.reload_from_file(base_path, preserve_camera=True, is_new_base=True)

            if self.on_reload_callback:
                self.on_reload_callback(base_path)

            self._load_advances()

            messagebox.showinfo(
                "Base PLY Overwritten",
                f"Base file '{os.path.basename(base_path)}' has been overwritten successfully.\n"
                f"Safety backup created at '{os.path.basename(bak_path)}'.",
                parent=self
            )
        except Exception as e:
            messagebox.showerror("Overwrite Error", f"Failed to overwrite base file: {str(e)}", parent=self)

    def restore_base_ply(self):
        """Restore base PLY file from backup or reload base file into viewer."""
        base_path = self.pc.filename
        if not base_path:
            messagebox.showerror("Base File Not Found", "Base file is not specified.", parent=self)
            return

        bak_path = base_path + ".bak"
        has_bak = os.path.isfile(bak_path)

        msg = f"Do you want to reload the base file '{os.path.basename(base_path)}' into the viewer?"
        if has_bak:
            msg += f"\n\nNote: A backup file '{os.path.basename(bak_path)}' is available. " \
                   "Would you like to restore from this backup before reloading?"

        confirm = messagebox.askyesno("Restore Base PLY", msg, parent=self)
        if not confirm:
            return

        try:
            if has_bak:
                # Restore backup to base
                shutil.copy2(bak_path, base_path)

            # Reload into pc as new base
            self.pc.reload_from_file(base_path, preserve_camera=True, is_new_base=True)

            if self.on_reload_callback:
                self.on_reload_callback(base_path)

            self._load_advances()

            messagebox.showinfo(
                "Base Restored",
                f"Base file '{os.path.basename(base_path)}' has been restored and loaded into viewer.",
                parent=self
            )
        except Exception as e:
            messagebox.showerror("Restore Error", f"Failed to restore base file: {str(e)}", parent=self)
