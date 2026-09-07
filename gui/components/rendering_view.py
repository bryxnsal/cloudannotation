"""
RenderingView: Component for [RENDER & CAMERA] section.
Controls point cloud rendering, work area isolation (Select/Unselect), inverted selection, and multi-label filtering.
"""
import tkinter as tk
from tkinter import ttk
import Config
from gui.components.base_component import BaseComponent

class RenderingView(BaseComponent):
    """
    Manages camera views, point isolation and multi-label selection filters.
    """
    def __init__(self, parent, app, pc, **kwargs):
        super().__init__(parent, app, pc, **kwargs)
        self._create_widgets()

    def _create_widgets(self):
        section_frame = ttk.LabelFrame(
            self,
            text=" [RENDER & CAMERA] ",
            style='Modern.TLabelframe',
            padding=10
        )
        section_frame.pack(fill='x')

        # Dynamic Point Size Slider + Textbox control (at the top of [RENDER & CAMERA])
        ptsize_row = ttk.Frame(section_frame, style='Modern.TFrame')
        ptsize_row.pack(fill='x', pady=(0, 6))

        ttk.Label(
            ptsize_row,
            text="Pt Size:",
            style='Title.TLabel',
            font=('Segoe UI', 9, 'bold')
        ).pack(side='left', padx=(0, 6))

        initial_size = getattr(self.pc, 'point_size', 0.005) if self.pc else 0.005
        self.ptsize_var = tk.StringVar(value="{:.3f}".format(initial_size))
        self._updating_ptsize = False

        self.ptsize_scale = ttk.Scale(
            ptsize_row,
            from_=0.001,
            to=0.080,
            orient='horizontal',
            command=self._on_scale_change
        )
        self.ptsize_scale.set(initial_size)
        self.ptsize_scale.pack(side='left', fill='x', expand=True, padx=(0, 6))

        self.ptsize_entry = ttk.Entry(
            ptsize_row,
            textvariable=self.ptsize_var,
            width=6,
            font=('Segoe UI', 9)
        )
        self.ptsize_entry.pack(side='right')
        self.ptsize_entry.bind('<Return>', lambda e: self._on_entry_submit())
        self.ptsize_entry.bind('<FocusOut>', lambda e: self._on_entry_submit())

        # Button row: All, Select, Select Inv, Multi
        button_row = ttk.Frame(section_frame, style='Modern.TFrame')
        button_row.pack(fill='x', pady=(0, 6))

        ttk.Button(
            button_row,
            text="All",
            command=self.render_all
        ).pack(side='left', padx=(0, 2), fill='x', expand=True)

        self.select_btn = ttk.Button(
            button_row,
            text="Select",
            command=self.toggle_selection_mode
        )
        self.select_btn.pack(side='left', padx=(2, 2), fill='x', expand=True)

        ttk.Button(
            button_row,
            text="Select Inv",
            command=self.render_selection_inv
        ).pack(side='left', padx=(2, 2), fill='x', expand=True)

        ttk.Button(
            button_row,
            text="Multi",
            command=self.render_selected_labels
        ).pack(side='right', padx=(2, 0), fill='x', expand=True)

        # Listbox with scrollbar for labels
        list_frame = ttk.Frame(section_frame, style='Modern.TFrame')
        list_frame.pack(fill='x', pady=(0, 6))

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side='right', fill='y')

        self.label_listbox = tk.Listbox(
            list_frame,
            selectmode=tk.MULTIPLE,
            height=4,
            bg=self.colors['bg_accent'],
            fg=self.colors['text_primary'],
            selectbackground=self.colors['accent'],
            font=('Segoe UI', 9),
            borderwidth=1,
            relief='solid',
            yscrollcommand=scrollbar.set
        )
        self.label_listbox.pack(side='left', fill='x', expand=True)
        scrollbar.config(command=self.label_listbox.yview)

        # Populate listbox
        for label in Config.labels.keys():
            self.label_listbox.insert(tk.END, label)

        # Bottom row: Select All / Clear selections
        sel_buttons_row = ttk.Frame(section_frame, style='Modern.TFrame')
        sel_buttons_row.pack(fill='x')

        ttk.Button(
            sel_buttons_row,
            text="Select All Labels",
            command=self.select_all_labels
        ).pack(side='left', padx=(0, 2), fill='x', expand=True)

        ttk.Button(
            sel_buttons_row,
            text="Clear Selections",
            command=self.clear_label_selections
        ).pack(side='right', padx=(2, 0), fill='x', expand=True)

    def _get_keep_camera(self):
        """Retrieve keep camera checkbox state from classification view."""
        if hasattr(self.app, 'classification_view'):
            return self.app.classification_view.keep_camera_var.get()
        return True

    def render_all(self):
        """Render all points in the point cloud and clear isolated work area."""
        keep_cam = self._get_keep_camera()
        def task():
            if self.pc.is_work_area_active():
                self.pc.clear_work_area()
            self.pc.render(preserve_camera=keep_cam)

        def on_done(_):
            self.select_btn.configure(text="Select")

        self.run_async(
            task,
            start_msg="Rendering full point cloud...",
            success_msg="Point cloud rendered successfully",
            on_success=on_done
        )

    def toggle_selection_mode(self):
        """Toggle between isolated work area and full view."""
        keep_cam = self._get_keep_camera()
        if self.pc.is_work_area_active():
            def task():
                self.pc.clear_work_area()
                self.pc.render(preserve_camera=keep_cam)

            def on_done(_):
                self.select_btn.configure(text="Select")

            self.run_async(
                task,
                start_msg="Restoring full point cloud...",
                success_msg="Exited isolated work area",
                on_success=on_done
            )
        else:
            if not self.pc.has_selection():
                self.log_message("No points are currently selected. Use Ctrl + Left Click to select points first.", "WARNING")
                return

            def task():
                mask = self.pc.get_highlighted_mask()
                self.pc.set_work_area(mask)
                self.pc.render(mask, preserve_camera=keep_cam)

            def on_done(_):
                self.select_btn.configure(text="Unselect")

            self.run_async(
                task,
                start_msg="Isolating selected work area...",
                success_msg="Work area isolated (Use Multi to filter within this area, or Unselect to exit)",
                on_success=on_done
            )

    def render_selection_inv(self):
        """Isolate inverted selection."""
        keep_cam = self._get_keep_camera()
        if not self.pc.has_selection():
            self.log_message("No points are currently selected to invert. Use Ctrl + Left Click to select points first.", "WARNING")
            return

        def task():
            mask = self.pc.get_highlighted_mask(invert=True)
            self.pc.set_work_area(mask)
            self.pc.render(mask, preserve_camera=keep_cam)

        def on_done(_):
            self.select_btn.configure(text="Unselect")

        self.run_async(
            task,
            start_msg="Isolating inverted selection...",
            success_msg="Inverted work area isolated",
            on_success=on_done
        )

    def render_selected_labels(self):
        """Render points matching selected labels in listbox."""
        selected_indices = self.label_listbox.curselection()
        if not selected_indices:
            self.log_message("No labels selected for rendering", "WARNING")
            return

        selected_labels = [Config.labels[self.label_listbox.get(i)] for i in selected_indices]
        keep_cam = self._get_keep_camera()

        def task():
            if self.pc.is_work_area_active():
                mask = self.pc.select(classes=selected_labels, highlighted=False)
                mask.intersection(self.pc.active_roi.bools)
            else:
                mask = self.pc.select(classes=selected_labels, highlighted=False)

            import numpy as np
            if np.sum(mask.bools) > 0:
                self.pc.render(mask, preserve_camera=keep_cam)
                return True
            return False

        def on_done(has_points):
            if self.pc.is_work_area_active():
                self.select_btn.configure(text="Unselect")
            else:
                self.select_btn.configure(text="Select")

            if not has_points:
                self.log_message("No points found for selected labels", "WARNING")

        self.run_async(
            task,
            start_msg="Rendering {} selected labels...".format(len(selected_labels)),
            success_msg="Multi-label rendering completed",
            on_success=on_done
        )

    def select_all_labels(self):
        self.label_listbox.select_set(0, tk.END)
        count = self.label_listbox.size()
        self.log_message("Selected all {} labels".format(count), "INFO")

    def clear_label_selections(self):
        self.label_listbox.selection_clear(0, tk.END)
        self.log_message("Cleared all label selections", "INFO")

    # ------------------ Dynamic Point Size Handlers ------------------
    def _on_scale_change(self, val):
        """Called when user drags or clicks the point size scale."""
        if self._updating_ptsize:
            return
        try:
            f_val = round(float(val), 4)
            self._updating_ptsize = True
            self.ptsize_var.set("{:.3f}".format(f_val))
            self._updating_ptsize = False

            if self.pc:
                self.pc.set_point_size(f_val)
            if hasattr(self.app, 'update_cloud_info'):
                self.app.update_cloud_info()
        except Exception as e:
            self._updating_ptsize = False
            self.log_message("Error changing point size: {}".format(e), "ERROR")

    def _on_entry_submit(self):
        """Called when user presses Enter or leaves focus on the point size entry."""
        if self._updating_ptsize:
            return
        try:
            raw_text = self.ptsize_var.get().strip()
            f_val = float(raw_text)
            f_val = max(0.001, min(0.100, f_val))
            f_val = round(f_val, 4)

            self._updating_ptsize = True
            self.ptsize_scale.set(f_val)
            self.ptsize_var.set("{:.3f}".format(f_val))
            self._updating_ptsize = False

            if self.pc:
                self.pc.set_point_size(f_val)
            if hasattr(self.app, 'update_cloud_info'):
                self.app.update_cloud_info()
        except ValueError:
            # Revert to current scale value if invalid input
            curr = self.ptsize_scale.get()
            self._updating_ptsize = True
            self.ptsize_var.set("{:.3f}".format(curr))
            self._updating_ptsize = False
        except Exception as e:
            self._updating_ptsize = False
            self.log_message("Error updating point size: {}".format(e), "ERROR")

    def update_point_size(self, size):
        """Update slider and entry widgets programmatically (e.g. from cloud reload)."""
        if size is None or self._updating_ptsize:
            return
        try:
            f_val = float(size)
            self._updating_ptsize = True
            self.ptsize_scale.set(f_val)
            self.ptsize_var.set("{:.3f}".format(f_val))
            self._updating_ptsize = False
        except Exception:
            self._updating_ptsize = False
