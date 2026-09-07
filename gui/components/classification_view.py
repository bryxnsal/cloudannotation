"""
ClassificationView: Component for [CLASS] section.
Handles class selection combobox, Overwrite and Keep Camera checkboxes, Execute and Undo actions.
"""
import tkinter as tk
from tkinter import ttk
import Config
from gui.components.base_component import BaseComponent

class ClassificationView(BaseComponent):
    """
    Manages point classification assignment and undo operations.
    """
    def __init__(self, parent, app, pc, **kwargs):
        super().__init__(parent, app, pc, **kwargs)

        self.option_var = tk.StringVar(self)
        self.option_var.set("")
        self.overwrite_var = tk.BooleanVar(self, value=False)
        self.keep_camera_var = tk.BooleanVar(self, value=True)

        self._create_widgets()

    def _create_widgets(self):
        section_frame = ttk.LabelFrame(
            self,
            text=" [CLASS] ",
            style='Modern.TLabelframe',
            padding=10
        )
        section_frame.pack(fill='x')

        # Top row: Combobox and Execute
        top_row = ttk.Frame(section_frame, style='Modern.TFrame')
        top_row.pack(fill='x', pady=(0, 8))

        self.class_combo = ttk.Combobox(
            top_row,
            textvariable=self.option_var,
            values=list(Config.labels.keys()),
            state='readonly',
            font=('Segoe UI', 10)
        )
        self.class_combo.pack(side='left', fill='x', expand=True, padx=(0, 6), ipady=2)

        ttk.Button(
            top_row,
            text="Execute",
            style='Accent.TButton',
            command=self.execute_selection
        ).pack(side='right')

        # Bottom row: Checkboxes, Shortcuts button, and Undo button
        options_row = ttk.Frame(section_frame, style='Modern.TFrame')
        options_row.pack(fill='x')

        ttk.Checkbutton(
            options_row,
            text="Overwrite",
            variable=self.overwrite_var,
            style='Modern.TCheckbutton'
        ).pack(side='left', padx=(0, 14))

        ttk.Checkbutton(
            options_row,
            text="Keep Camera Position",
            variable=self.keep_camera_var,
            style='Modern.TCheckbutton'
        ).pack(side='left')

        ttk.Button(
            options_row,
            text="Undo",
            command=self.undo_action
        ).pack(side='right', padx=(6, 0))

        self.shortcuts_btn = ttk.Button(
            options_row,
            text="⚙ Shortcuts",
            command=self.open_shortcuts_modal
        )
        self.shortcuts_btn.pack(side='right', padx=(6, 0))

    def execute_selection(self):
        """Classify selected points with active label."""
        selected_option = self.option_var.get()
        overwrite = self.overwrite_var.get()
        keep_cam = self.keep_camera_var.get()

        if not selected_option:
            self.log_message("No classification option selected", "WARNING")
            return

        if not self.pc.has_selection():
            self.log_message("No points are currently selected. Use Ctrl + Left Click to select points first.", "WARNING")
            return

        label_value = Config.labels[selected_option]
        success_msg = "Classified as {} (Label {})".format(selected_option, label_value)
        if overwrite:
            success_msg += " [Overwritten]"

        def on_done(_):
            self.update_cloud_info()

        self.run_async(
            lambda: self.pc.classify(label_value, overwrite=overwrite, preserve_camera=keep_cam),
            start_msg="Classifying: {} (Label {})...".format(selected_option, label_value),
            success_msg=success_msg,
            on_success=on_done
        )

    def undo_action(self):
        """Undo last classification action."""
        def task():
            return self.pc.undo()

        def on_done(res):
            self.update_cloud_info()
            if res:
                success, msg = res
                self.log_message(msg, "SUCCESS" if success else "WARNING")

        self.run_async(
            task,
            start_msg="Undoing last action...",
            on_success=on_done
        )

    def redo_action(self):
        """Redo last undone classification action."""
        def task():
            return self.pc.redo()

        def on_done(res):
            self.update_cloud_info()
            if res:
                success, msg = res
                self.log_message(msg, "SUCCESS" if success else "WARNING")

        self.run_async(
            task,
            start_msg="Redoing action...",
            on_success=on_done
        )

    def set_selected_class(self, class_name):
        """Set active class in combobox."""
        if class_name in Config.labels:
            self.option_var.set(class_name)

    def open_shortcuts_modal(self):
        """Open the shortcuts configuration dialog."""
        self.app.open_shortcuts_modal()
