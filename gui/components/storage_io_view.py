"""
StorageIoView: Component for [I/O] section.
Handles saving progress advances, exporting results, and launching the Advances List modal.
"""
from tkinter import ttk
from gui.components.base_component import BaseComponent

class StorageIoView(BaseComponent):
    """
    Manages persistence operations and advances inspection.
    """
    def __init__(self, parent, app, pc, **kwargs):
        super().__init__(parent, app, pc, **kwargs)
        self._create_widgets()

    def _create_widgets(self):
        section_frame = ttk.LabelFrame(
            self,
            text=" [I/O] ",
            style='Modern.TLabelframe',
            padding=10
        )
        section_frame.pack(fill='x')

        row1 = ttk.Frame(section_frame, style='Modern.TFrame')
        row1.pack(fill='x', pady=(0, 4))

        ttk.Button(
            row1,
            text="Open PLY",
            style='Accent.TButton',
            command=self.open_ply_file
        ).pack(side='left', padx=(0, 4), fill='x', expand=True)

        ttk.Button(
            row1,
            text="Save Advance",
            command=self.save_progress
        ).pack(side='left', padx=(0, 4), fill='x', expand=True)

        ttk.Button(
            row1,
            text="Export Result",
            command=self.export_result
        ).pack(side='right', fill='x', expand=True)

        row2 = ttk.Frame(section_frame, style='Modern.TFrame')
        row2.pack(fill='x')

        ttk.Button(
            row2,
            text="Advances List",
            command=self.open_advances_modal
        ).pack(fill='x', expand=True)

    def open_ply_file(self):
        """Prompt file dialog to open and load any PLY point cloud."""
        self.app.open_ply_dialog()

    def save_progress(self):
        """Save current progress as a new advance."""
        def on_saved(_):
            self.update_cloud_info()

        self.run_async(
            lambda: self.pc.save(),
            start_msg="Saving advance...",
            success_msg="Progress saved successfully",
            on_success=on_saved
        )

    def export_result(self):
        """Export classified results."""
        self.run_async(
            lambda: self.pc.export(),
            start_msg="Exporting results...",
            success_msg="Export completed successfully"
        )

    def open_advances_modal(self):
        """Open the Advances List modal dialog."""
        self.app.open_advances_modal()
