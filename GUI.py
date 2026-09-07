import tkinter as tk
from tkinter import ttk
import datetime
import threading
import Config
from PointCloud import PointCloud
from AdvancesModal import AdvancesModal

class ModernAnnotationGUI:
    def __init__(self, pc: PointCloud):
        self.root = tk.Tk()
        self.root.title("Point Cloud Annotator")
        self.root.geometry("520x720")
        self.root.configure(bg='#2b2b2b')
        
        # Make window always on top
        self.root.attributes('-topmost', True)
        
        self.pc = pc

        # Modern color scheme
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

        # Configure style
        self.setup_styles()

        # Variables
        self.option_var = tk.StringVar(self.root)
        self.option_var.set("")
        self.overwrite_var = tk.BooleanVar(self.root, value=False)
        self.keep_camera_var = tk.BooleanVar(self.root, value=True)
        self.show_logs = tk.BooleanVar(self.root, value=False)

        # Global Keyboard Shortcuts
        self.root.bind('<Control-z>', lambda e: self.undo_action())
        self.root.bind('<Control-Z>', lambda e: self.undo_action())
        self.root.bind('<Control-y>', lambda e: self.redo_action())
        self.root.bind('<Control-Y>', lambda e: self.redo_action())

        # Status tracking
        self.status_messages = []

        # Window close handler
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Build GUI
        self._create_widgets()
        
        # Add initial log message
        self.log_message("System initialized", "INFO")

    def on_close(self):
        """Handle window closing gracefully."""
        try:
            if self.pc:
                self.pc.close_viewer()
        except Exception:
            pass
        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass
        import os
        os._exit(0)

    def setup_styles(self):
        """Configure modern ttk styles with larger readable fonts."""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure colors and larger fonts
        style.configure('Modern.TFrame', background=self.colors['bg_secondary'])
        style.configure('Accent.TFrame', background=self.colors['bg_accent'])
        style.configure('Modern.TLabelframe', background=self.colors['bg_secondary'], bordercolor=self.colors['border'])
        style.configure('Modern.TLabelframe.Label', background=self.colors['bg_secondary'], 
                        foreground=self.colors['text_primary'], font=('Segoe UI', 10, 'bold'))
        style.configure('Modern.TLabel', background=self.colors['bg_secondary'], 
                        foreground=self.colors['text_primary'], font=('Segoe UI', 10))
        style.configure('Title.TLabel', background=self.colors['bg_secondary'], 
                        foreground=self.colors['text_primary'], font=('Segoe UI', 10, 'bold'))
        style.configure('Modern.TButton', font=('Segoe UI', 10), padding=4)
        style.configure('Accent.TButton', font=('Segoe UI', 10, 'bold'), padding=4)
        style.configure('Modern.TCheckbutton', background=self.colors['bg_secondary'],
                        foreground=self.colors['text_primary'], font=('Segoe UI', 10))
        style.configure('Modern.Horizontal.TProgressbar', 
                        background=self.colors['accent'], 
                        troughcolor=self.colors['bg_primary'],
                        bordercolor=self.colors['border'],
                        lightcolor=self.colors['accent'],
                        darkcolor=self.colors['accent'])

    def _create_widgets(self):
        """Create modern GUI layout."""
        # Main container
        main_frame = ttk.Frame(self.root, style='Modern.TFrame')
        main_frame.pack(fill='both', expand=True, padx=12, pady=12)

        # Control sections
        self._create_info_section(main_frame)
        self._create_classification_section(main_frame)
        self._create_ai_tools_section(main_frame)
        self._create_rendering_section(main_frame)
        self._create_save_export_section(main_frame)

        # Compact status at bottom
        self._create_status_section(main_frame)

        # Initialize info display
        self.update_cloud_info()

    def _create_info_section(self, parent):
        """Create [INFO] section with PLY point cloud metadata."""
        section_frame = ttk.LabelFrame(parent, text=" [INFO] ", 
                                       style='Modern.TLabelframe', padding=8)
        section_frame.pack(fill='x', pady=(0, 8))

        # Grid configuration for clean aligned layout
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

        # Row 2: Date and Modified vs Base stats
        ttk.Label(grid_frame, text="Date:", style='Title.TLabel', font=('Segoe UI', 9, 'bold')).grid(row=2, column=0, sticky='w', padx=(0, 4), pady=(2, 0))
        self.info_date_lbl = ttk.Label(grid_frame, text="-", style='Modern.TLabel', font=('Segoe UI', 9))
        self.info_date_lbl.grid(row=2, column=1, sticky='w', padx=(0, 10), pady=(2, 0))

        ttk.Label(grid_frame, text="Modified:", style='Title.TLabel', font=('Segoe UI', 9, 'bold')).grid(row=2, column=2, sticky='w', padx=(0, 4), pady=(2, 0))
        self.info_modified_lbl = ttk.Label(grid_frame, text="-", style='Modern.TLabel', font=('Segoe UI', 9))
        self.info_modified_lbl.grid(row=2, column=3, sticky='w', pady=(2, 0))

    def update_cloud_info(self):
        """Fetch stats from PointCloud and update [INFO] UI labels."""
        try:
            stats = self.pc.get_stats()
            fname = stats['filename']
            if len(fname) > 22:
                fname = fname[:10] + "..." + fname[-9:]
            self.info_file_lbl.configure(text=fname)

            self.info_size_lbl.configure(text=f"{stats['file_size_mb']:.1f} MB")
            self.info_points_lbl.configure(text=f"{stats['total_points']:,}")
            self.info_ptsize_lbl.configure(text=f"{stats['point_size']}")

            if stats['mtime']:
                self.info_date_lbl.configure(text=stats['mtime'].strftime("%Y-%m-%d %H:%M"))
            else:
                self.info_date_lbl.configure(text="N/A")

            changed_pts = stats.get('changed_points', 0)
            changed_ratio = stats.get('changed_ratio', 0.0)
            if changed_pts > 0:
                self.info_modified_lbl.configure(text=f"{changed_pts:,} ({changed_ratio:.2f}%)")
            else:
                self.info_modified_lbl.configure(text="0 (0.0%)")
        except Exception as e:
            print("Error updating cloud info:", e)

    def _create_classification_section(self, parent):
        """Create classification and camera behavior section."""
        section_frame = ttk.LabelFrame(parent, text=" [CLASS] ", 
                                       style='Modern.TLabelframe', padding=10)
        section_frame.pack(fill='x', pady=(0, 8))

        # Class selection and Execute button
        top_row = ttk.Frame(section_frame, style='Modern.TFrame')
        top_row.pack(fill='x', pady=(0, 8))
        
        self.class_combo = ttk.Combobox(top_row, textvariable=self.option_var, 
                                        values=list(Config.labels.keys()), 
                                        state='readonly', font=('Segoe UI', 10))
        self.class_combo.pack(side='left', fill='x', expand=True, padx=(0, 6), ipady=2)

        ttk.Button(top_row, text="Execute", style='Accent.TButton',
                   command=self.execute_selection).pack(side='right')

        # Checkboxes row: Overwrite & Keep Camera Position and Undo button
        options_row = ttk.Frame(section_frame, style='Modern.TFrame')
        options_row.pack(fill='x')

        ttk.Checkbutton(options_row, text="Overwrite", 
                        variable=self.overwrite_var,
                        style='Modern.TCheckbutton').pack(side='left', padx=(0, 14))

        ttk.Checkbutton(options_row, text="Keep Camera Position", 
                        variable=self.keep_camera_var,
                        style='Modern.TCheckbutton').pack(side='left')

        ttk.Button(options_row, text="Undo", 
                   command=self.undo_action).pack(side='right', padx=(10, 0))

    def _create_rendering_section(self, parent):
        """Create rendering and camera view section."""
        section_frame = ttk.LabelFrame(parent, text=" [RENDER & CAMERA] ", 
                                       style='Modern.TLabelframe', padding=10)
        section_frame.pack(fill='x', pady=(0, 8))

        # Render buttons
        button_row = ttk.Frame(section_frame, style='Modern.TFrame')
        button_row.pack(fill='x', pady=(0, 6))
        
        ttk.Button(button_row, text="All", 
                   command=self.render_all).pack(side='left', padx=(0, 2), fill='x', expand=True)
        self.select_btn = ttk.Button(button_row, text="Select", 
                                     command=self.toggle_selection_mode)
        self.select_btn.pack(side='left', padx=(2, 2), fill='x', expand=True)
        ttk.Button(button_row, text="Select Inv", 
                   command=self.render_selection_inv).pack(side='left', padx=(2, 2), fill='x', expand=True)
        ttk.Button(button_row, text="Multi", 
                   command=self.render_selected_labels).pack(side='right', padx=(2, 0), fill='x', expand=True)

        # Listbox with scrollbar
        list_frame = ttk.Frame(section_frame, style='Modern.TFrame')
        list_frame.pack(fill='x', pady=(0, 6))

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side='right', fill='y')

        self.label_listbox = tk.Listbox(list_frame, selectmode=tk.MULTIPLE, 
                                        height=4, bg=self.colors['bg_accent'], 
                                        fg=self.colors['text_primary'],
                                        selectbackground=self.colors['accent'],
                                        font=('Segoe UI', 9), borderwidth=1, relief='solid',
                                        yscrollcommand=scrollbar.set)
        self.label_listbox.pack(side='left', fill='x', expand=True)
        scrollbar.config(command=self.label_listbox.yview)

        # Populate listbox
        for label in Config.labels.keys():
            self.label_listbox.insert(tk.END, label)

        # Selection buttons row
        sel_buttons_row = ttk.Frame(section_frame, style='Modern.TFrame')
        sel_buttons_row.pack(fill='x')

        ttk.Button(sel_buttons_row, text="Select All Labels", 
                   command=self.select_all_labels).pack(side='left', padx=(0, 2), fill='x', expand=True)
        ttk.Button(sel_buttons_row, text="Clear Selections", 
                   command=self.clear_label_selections).pack(side='right', padx=(2, 0), fill='x', expand=True)

    def _create_ai_tools_section(self, parent):
        """Create experimental AI and assisted tools section."""
        section_frame = ttk.LabelFrame(parent, text=" [AI TOOLS (EXPERIMENTAL)] ", 
                                       style='Modern.TLabelframe', padding=10)
        section_frame.pack(fill='x', pady=(0, 8))

        row1 = ttk.Frame(section_frame, style='Modern.TFrame')
        row1.pack(fill='x', pady=(0, 4))

        ttk.Button(row1, text="Auto Ground", 
                   command=self.ai_auto_ground_action).pack(side='left', padx=(0, 2), fill='x', expand=True)
        ttk.Button(row1, text="Classify Pole", 
                   command=self.ai_classify_pole_action).pack(side='right', padx=(2, 0), fill='x', expand=True)

        row2 = ttk.Frame(section_frame, style='Modern.TFrame')
        row2.pack(fill='x')

        ttk.Button(row2, text="Grow Cable", 
                   command=self.ai_grow_cable_action).pack(side='left', padx=(0, 2), fill='x', expand=True)
        ttk.Button(row2, text="Classify Veg", 
                   command=self.ai_classify_veg_action).pack(side='right', padx=(2, 0), fill='x', expand=True)

    def _create_save_export_section(self, parent):
        """Create save/export section."""
        section_frame = ttk.LabelFrame(parent, text=" [I/O] ", 
                                       style='Modern.TLabelframe', padding=10)
        section_frame.pack(fill='x', pady=(0, 8))

        row1 = ttk.Frame(section_frame, style='Modern.TFrame')
        row1.pack(fill='x', pady=(0, 4))
        
        ttk.Button(row1, text="Save Advance", 
                   command=self.save_progress).pack(side='left', padx=(0, 4), fill='x', expand=True)
        ttk.Button(row1, text="Export Result", 
                   command=self.export_result).pack(side='right', padx=(4, 0), fill='x', expand=True)

        row2 = ttk.Frame(section_frame, style='Modern.TFrame')
        row2.pack(fill='x')

        ttk.Button(row2, text="Advances List", 
                   command=self.open_advances_modal).pack(fill='x', expand=True)

    def _create_status_section(self, parent):
        """Create progress bar and toggleable status section."""
        # Progress bar container
        progress_frame = ttk.Frame(parent, style='Modern.TFrame')
        progress_frame.pack(fill='x', pady=(4, 4))
        
        # Starts completely empty in determinate mode with value=0
        self.progress_bar = ttk.Progressbar(progress_frame,
                                            orient='horizontal',
                                            mode='determinate',
                                            maximum=100,
                                            value=0,
                                            style='Modern.Horizontal.TProgressbar')
        self.progress_bar.pack(fill='x', expand=True, ipady=1)

        # Status bar with toggle button
        status_bar = ttk.Frame(parent, style='Accent.TFrame')
        status_bar.pack(fill='x', pady=(2, 0))
        
        # Current status
        self.status_label = ttk.Label(status_bar, text="Ready", 
                                      style='Modern.TLabel', font=('Consolas', 9))
        self.status_label.pack(side='left', padx=4, pady=2)
        
        # Toggle logs button
        self.toggle_btn = ttk.Button(status_bar, text="Log", width=5,
                                     command=self.toggle_logs)
        self.toggle_btn.pack(side='right', padx=2, pady=2)

        # Collapsible log frame with scrollbar
        self.log_frame = ttk.Frame(parent, style='Modern.TFrame')
        
        log_scroll = ttk.Scrollbar(self.log_frame)
        log_scroll.pack(side='right', fill='y')

        self.mini_log = tk.Text(self.log_frame, height=5, 
                                bg=self.colors['bg_primary'], 
                                fg=self.colors['text_secondary'],
                                font=('Consolas', 9), borderwidth=1, relief='solid',
                                wrap='word', state='disabled',
                                yscrollcommand=log_scroll.set)
        self.mini_log.pack(side='left', fill='both', expand=True, pady=(3, 0))
        log_scroll.config(command=self.mini_log.yview)
        
        # Configure colors
        self.mini_log.tag_configure('OK', foreground=self.colors['success'])
        self.mini_log.tag_configure('WARN', foreground=self.colors['warning'])
        self.mini_log.tag_configure('ERR', foreground=self.colors['error'])

    # ------------------ Progress Bar Helpers & Async Runner ------------------
    def start_progress(self, message=None):
        """Start smooth indeterminate progress animation."""
        if message:
            self.log_message(message, "INFO")
        self.progress_bar.config(mode='indeterminate')
        self.progress_bar.start(10)
        self.root.update_idletasks()

    def stop_progress(self, message=None, level="SUCCESS"):
        """Stop progress bar animation, reset to empty (value=0)."""
        self.progress_bar.stop()
        self.progress_bar.config(mode='determinate', value=0)
        if message:
            self.log_message(message, level)
        self.root.update_idletasks()

    def set_progress(self, value, maximum=100, message=None):
        """Set determinate progress value (0 to maximum)."""
        self.progress_bar.stop()
        self.progress_bar.config(mode='determinate', maximum=maximum, value=value)
        if message:
            self.log_message(message, "INFO")
        self.root.update_idletasks()

    def run_async(self, target_fn, start_msg=None, success_msg=None, on_success=None):
        """Run tasks in background thread so indeterminate progress bar animates fluidly."""
        def worker():
            try:
                res = target_fn()
                def on_done():
                    if on_success:
                        on_success(res)
                    self.stop_progress(success_msg, "SUCCESS")
                self.root.after(0, on_done)
            except Exception as e:
                err_msg = str(e)
                self.root.after(0, lambda: self.stop_progress(f"Error: {err_msg}", "ERROR"))

        self.start_progress(start_msg)
        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def toggle_logs(self):
        """Show/hide log section."""
        if self.show_logs.get():
            self.log_frame.pack_forget()
            self.toggle_btn.configure(text="Log")
            self.show_logs.set(False)
            self.root.geometry("520x720")
        else:
            self.log_frame.pack(fill='both', expand=True, pady=(3, 0))
            self.toggle_btn.configure(text="Hide")
            self.show_logs.set(True)
            self.root.geometry("520x840")

    def log_message(self, message, level="INFO"):
        """Add message to status bar and optional mini log."""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        
        status_colors = {
            'INFO': self.colors['text_primary'],
            'SUCCESS': self.colors['success'], 
            'WARNING': self.colors['warning'],
            'ERROR': self.colors['error']
        }
        self.status_label.configure(text=f"{timestamp} {message}", 
                                    foreground=status_colors.get(level, self.colors['text_primary']))
        
        if self.show_logs.get():
            self.mini_log.config(state='normal')
            
            level_map = {'INFO': 'OK', 'SUCCESS': 'OK', 'WARNING': 'WARN', 'ERROR': 'ERR'}
            short_level = level_map.get(level, 'OK')
            
            entry = f"{timestamp} {short_level}: {message}\n"
            self.mini_log.insert('end', entry, short_level)
            
            lines = self.mini_log.get('1.0', 'end').strip().split('\n')
            if len(lines) > 5:
                self.mini_log.delete('1.0', 'end')
                for line in lines[-5:]:
                    if line.strip():
                        level_tag = 'ERR' if 'ERR:' in line else ('WARN' if 'WARN:' in line else 'OK')
                        self.mini_log.insert('end', line + '\n', level_tag)
            
            self.mini_log.see('end')
            self.mini_log.config(state='disabled')

    def clear_logs(self):
        """Clear the mini log if visible."""
        if self.show_logs.get():
            self.mini_log.config(state='normal')
            self.mini_log.delete('1.0', 'end')
            self.mini_log.config(state='disabled')

    # ------------------ Classification Methods ------------------
    def execute_selection(self):
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
        success_msg = f"Classified as {selected_option} (Label {label_value})"
        if overwrite:
            success_msg += " [Overwritten]"

        def on_done(_):
            self.update_cloud_info()

        self.run_async(
            lambda: self.pc.classify(label_value, overwrite=overwrite, preserve_camera=keep_cam),
            start_msg=f"Classifying: {selected_option} (Label {label_value})...",
            success_msg=success_msg,
            on_success=on_done
        )

    def undo_action(self):
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

    # ------------------ Rendering Methods ------------------
    def render_all(self):
        keep_cam = self.keep_camera_var.get()
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
        keep_cam = self.keep_camera_var.get()
        if self.pc.is_work_area_active():
            # Exit work area mode and restore full view
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
            # Enter work area mode
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
        keep_cam = self.keep_camera_var.get()
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
        selected_indices = self.label_listbox.curselection()
        if not selected_indices:
            self.log_message("No labels selected for rendering", "WARNING")
            return
            
        selected_labels = [Config.labels[self.label_listbox.get(i)] for i in selected_indices]
        keep_cam = self.keep_camera_var.get()

        def task():
            if self.pc.is_work_area_active():
                # Filter only within the isolated work area
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
            start_msg=f"Rendering {len(selected_labels)} selected labels...",
            success_msg="Multi-label rendering completed",
            on_success=on_done
        )

    def select_all_labels(self):
        self.label_listbox.select_set(0, tk.END)
        count = self.label_listbox.size()
        self.log_message(f"Selected all {count} labels", "INFO")

    def clear_label_selections(self):
        self.label_listbox.selection_clear(0, tk.END)
        self.log_message("Cleared all label selections", "INFO")

    # ------------------ Save / Export Methods ------------------
    def save_progress(self):
        def on_saved(_):
            self.update_cloud_info()

        self.run_async(
            lambda: self.pc.save(),
            start_msg="Saving advance...",
            success_msg="Progress saved successfully",
            on_success=on_saved
        )

    def export_result(self):
        self.run_async(
            lambda: self.pc.export(),
            start_msg="Exporting results...",
            success_msg="Export completed successfully"
        )

    def open_advances_modal(self):
        """Open the Advances List modal window."""
        try:
            AdvancesModal(self.root, self.pc, on_reload_callback=self.on_cloud_reloaded)
        except Exception as e:
            self.log_message(f"Error opening advances modal: {str(e)}", "ERROR")

    def on_cloud_reloaded(self, filepath):
        """Callback invoked when an advance or base file is reloaded from the modal."""
        self.select_btn.configure(text="Select")
        self.update_cloud_info()
        self.log_message(f"Loaded point cloud: {datetime.datetime.now().strftime('%H:%M:%S')}", "SUCCESS")

    # ------------------ AI Assisted Methods ------------------
    def ai_auto_ground_action(self):
        overwrite = self.overwrite_var.get()
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
        overwrite = self.overwrite_var.get()
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
        overwrite = self.overwrite_var.get()
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
        overwrite = self.overwrite_var.get()
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

    def run(self):
        self.root.mainloop()