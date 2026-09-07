"""
AiToolsView: Component for [AI TOOLS (EXPERIMENTAL)] section.
Provides action buttons for assisted AI algorithms: Auto Ground, Classify Pole, Grow Cable, Classify Veg.
"""
from tkinter import ttk
from gui.components.base_component import BaseComponent

class AiToolsView(BaseComponent):
    """
    Experimental automated classification tools.
    """
    def __init__(self, parent, app, pc, **kwargs):
        super().__init__(parent, app, pc, **kwargs)
        self._create_widgets()

    def _create_widgets(self):
        section_frame = ttk.LabelFrame(
            self,
            text=" [AI TOOLS (EXPERIMENTAL)] ",
            style='Modern.TLabelframe',
            padding=10
        )
        section_frame.pack(fill='x')

        row1 = ttk.Frame(section_frame, style='Modern.TFrame')
        row1.pack(fill='x', pady=(0, 4))

        ttk.Button(
            row1,
            text="Auto Ground",
            command=self.ai_auto_ground_action
        ).pack(side='left', padx=(0, 2), fill='x', expand=True)

        ttk.Button(
            row1,
            text="Classify Pole",
            command=self.ai_classify_pole_action
        ).pack(side='right', padx=(2, 0), fill='x', expand=True)

        row2 = ttk.Frame(section_frame, style='Modern.TFrame')
        row2.pack(fill='x')

        ttk.Button(
            row2,
            text="Grow Cable",
            command=self.ai_grow_cable_action
        ).pack(side='left', padx=(0, 2), fill='x', expand=True)

        ttk.Button(
            row2,
            text="Classify Veg",
            command=self.ai_classify_veg_action
        ).pack(side='right', padx=(2, 0), fill='x', expand=True)

    def _get_overwrite(self):
        if hasattr(self.app, 'classification_view'):
            return self.app.classification_view.overwrite_var.get()
        return False

    def ai_auto_ground_action(self):
        overwrite = self._get_overwrite()
        def task():
            return self.pc.ai_auto_ground(overwrite=overwrite)

        def on_done(res):
            self.update_cloud_info()
            if res:
                success, msg = res
                self.log_message(msg, "SUCCESS" if success else "WARNING")

        self.run_async(
            task,
            start_msg="Detecting and fitting ground plane...",
            on_success=on_done
        )

    def ai_classify_pole_action(self):
        overwrite = self._get_overwrite()
        def task():
            return self.pc.ai_classify_pole(overwrite=overwrite)

        def on_done(res):
            self.update_cloud_info()
            if res:
                success, msg = res
                self.log_message(msg, "SUCCESS" if success else "WARNING")

        self.run_async(
            task,
            start_msg="Analyzing pole height and structure...",
            on_success=on_done
        )

    def ai_grow_cable_action(self):
        overwrite = self._get_overwrite()
        def task():
            return self.pc.ai_grow_cable(overwrite=overwrite)

        def on_done(res):
            self.update_cloud_info()
            if res:
                success, msg = res
                self.log_message(msg, "SUCCESS" if success else "WARNING")

        self.run_async(
            task,
            start_msg="Clustering linear cable points...",
            on_success=on_done
        )

    def ai_classify_veg_action(self):
        overwrite = self._get_overwrite()
        def task():
            return self.pc.ai_classify_veg(overwrite=overwrite)

        def on_done(res):
            self.update_cloud_info()
            if res:
                success, msg = res
                self.log_message(msg, "SUCCESS" if success else "WARNING")

        self.run_async(
            task,
            start_msg="Analyzing volumetric vegetation foliage...",
            on_success=on_done
        )
