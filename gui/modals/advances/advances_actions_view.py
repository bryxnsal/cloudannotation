"""
AdvancesActionsView: Action buttons bar for Advances Dialog.
Decoupled and purely event/callback driven.
"""
from tkinter import ttk

class AdvancesActionsView(ttk.Frame):
    """
    Bottom toolbar for advances actions: Load, Overwrite, Restore, Refresh, Close.
    """
    def __init__(
        self,
        parent,
        on_load=None,
        on_overwrite=None,
        on_restore=None,
        on_refresh=None,
        on_close=None,
        **kwargs
    ):
        super().__init__(parent, style='Modern.TFrame', **kwargs)
        self.on_load = on_load
        self.on_overwrite = on_overwrite
        self.on_restore = on_restore
        self.on_refresh = on_refresh
        self.on_close = on_close

        self._create_widgets()

    def _create_widgets(self):
        # Left action buttons
        self.load_btn = ttk.Button(
            self,
            text="Load Advance in Viewer",
            style='Accent.TButton',
            command=self.on_load
        )
        self.load_btn.pack(side='left', padx=(0, 6))

        self.overwrite_btn = ttk.Button(
            self,
            text="Overwrite Base PLY",
            command=self.on_overwrite
        )
        self.overwrite_btn.pack(side='left', padx=(0, 6))

        self.restore_btn = ttk.Button(
            self,
            text="Restore Base PLY",
            command=self.on_restore
        )
        self.restore_btn.pack(side='left', padx=(0, 6))

        # Right buttons
        if self.on_close:
            self.close_btn = ttk.Button(
                self,
                text="Close",
                command=self.on_close
            )
            self.close_btn.pack(side='right', padx=(6, 0))

        if self.on_refresh:
            self.refresh_btn = ttk.Button(
                self,
                text="Refresh",
                command=self.on_refresh
            )
            self.refresh_btn.pack(side='right')
