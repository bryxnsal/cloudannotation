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
