import tkinter as tk
from tkinter import ttk
import datetime
import threading
import Config
from PointCloud import PointCloud

class ModernAnnotationGUI:
    def __init__(self, pc: PointCloud):
        self.root = tk.Tk()
        self.root.title("Point Cloud Annotator")
        self.root.geometry("490x530")
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

        # Status tracking
        self.status_messages = []

        # Build GUI
        self._create_widgets()
        
        # Add initial log message
        self.log_message("System initialized", "INFO")

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
        self._create_classification_section(main_frame)
        self._create_rendering_section(main_frame)
        self._create_save_export_section(main_frame)

        # Compact status at bottom
        self._create_status_section(main_frame)

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

        # Checkboxes row: Overwrite & Keep Camera Position
        options_row = ttk.Frame(section_frame, style='Modern.TFrame')
        options_row.pack(fill='x')

        ttk.Checkbutton(options_row, text="Overwrite", 
                        variable=self.overwrite_var,
                        style='Modern.TCheckbutton').pack(side='left', padx=(0, 14))

        ttk.Checkbutton(options_row, text="Keep Camera Position", 
                        variable=self.keep_camera_var,
                        style='Modern.TCheckbutton').pack(side='left')

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
        ttk.Button(button_row, text="Select", 
                   command=self.render_selection).pack(side='left', padx=(2, 2), fill='x', expand=True)
        ttk.Button(button_row, text="Select Inv", 
                   command=self.render_selection_inv).pack(side='left', padx=(2, 2), fill='x', expand=True)
        ttk.Button(button_row, text="Multi", 
                   command=self.render_selected_labels).pack(side='right', padx=(2, 0), fill='x', expand=True)

        # Camera Save / Load buttons
        cam_row = ttk.Frame(section_frame, style='Modern.TFrame')
        cam_row.pack(fill='x', pady=(0, 6))

        ttk.Button(cam_row, text="Save Cam", 
                   command=self.save_camera_view).pack(side='left', padx=(0, 2), fill='x', expand=True)
        ttk.Button(cam_row, text="Load Cam", 
                   command=self.restore_camera_view).pack(side='right', padx=(2, 0), fill='x', expand=True)

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

        # Select all button
        ttk.Button(section_frame, text="Select All Labels", 
                   command=self.select_all_labels).pack(fill='x')

    def _create_save_export_section(self, parent):
        """Create save/export section."""
        section_frame = ttk.LabelFrame(parent, text=" [I/O] ", 
                                       style='Modern.TLabelframe', padding=10)
        section_frame.pack(fill='x', pady=(0, 8))

        button_row = ttk.Frame(section_frame, style='Modern.TFrame')
        button_row.pack(fill='x')
        
        ttk.Button(button_row, text="Save Advance", 
                   command=self.save_progress).pack(side='left', padx=(0, 4), fill='x', expand=True)
        ttk.Button(button_row, text="Export Result", 
                   command=self.export_result).pack(side='right', padx=(4, 0), fill='x', expand=True)

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

        # Collapsible log frame
        self.log_frame = ttk.Frame(parent, style='Accent.TFrame')
        
        self.mini_log = tk.Text(self.log_frame, height=3, 
                                bg=self.colors['bg_primary'], 
                                fg=self.colors['text_secondary'],
                                font=('Consolas', 8), borderwidth=1, relief='solid',
                                wrap='word', state='disabled')
        self.mini_log.pack(fill='x', pady=(3, 0))
        
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
            self.root.geometry("490x540")
        else:
            self.log_frame.pack(fill='x', pady=(3, 0))
            self.toggle_btn.configure(text="Hide")
            self.show_logs.set(True)
            self.root.geometry("490x610")

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
            
        label_value = Config.labels[selected_option]
        success_msg = f"Classified as {selected_option} (Label {label_value})"
        if overwrite:
            success_msg += " [Overwritten]"

        self.run_async(
            lambda: self.pc.classify(label_value, overwrite=overwrite, preserve_camera=keep_cam),
            start_msg=f"Classifying: {selected_option} (Label {label_value})...",
            success_msg=success_msg
        )

    # ------------------ Rendering Methods ------------------
    def render_all(self):
        keep_cam = self.keep_camera_var.get()
        self.run_async(
            lambda: self.pc.render(preserve_camera=keep_cam),
            start_msg="Rendering full point cloud...",
            success_msg="Point cloud rendered successfully"
        )

    def render_selection(self):
        keep_cam = self.keep_camera_var.get()
        self.run_async(
            lambda: self.pc.render(highlighted=True, preserve_camera=keep_cam),
            start_msg="Rendering selection...",
            success_msg="Selection rendered successfully"
        )

    def render_selection_inv(self):
        keep_cam = self.keep_camera_var.get()
        self.run_async(
            lambda: self.pc.render(highlighted=True, invert=True, preserve_camera=keep_cam),
            start_msg="Rendering inverted selection...",
            success_msg="Selection inverted successfully"
        )

    def render_selected_labels(self):
        selected_indices = self.label_listbox.curselection()
        if not selected_indices:
            self.log_message("No labels selected for rendering", "WARNING")
            return
            
        selected_labels = [Config.labels[self.label_listbox.get(i)] for i in selected_indices]
        keep_cam = self.keep_camera_var.get()

        def task():
            count = 0
            for lbl in selected_labels:
                count += (self.pc.points['class'] == lbl).sum()
            if count > 0:
                self.pc.render(self.pc.select(classes=selected_labels), preserve_camera=keep_cam)
                return True
            return False

        def on_done(has_points):
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

    # ------------------ Camera Methods ------------------
    def save_camera_view(self):
        try:
            persp = self.pc.save_camera('gui_cam')
            self.log_message("Camera position saved", "SUCCESS")
        except Exception as e:
            self.log_message(f"Failed to save camera: {str(e)}", "ERROR")

    def restore_camera_view(self):
        try:
            restored = self.pc.restore_camera('gui_cam')
            if restored:
                self.log_message("Camera position restored", "SUCCESS")
            else:
                self.log_message("No saved camera view found", "WARNING")
        except Exception as e:
            self.log_message(f"Failed to restore camera: {str(e)}", "ERROR")

    # ------------------ Save / Export Methods ------------------
    def save_progress(self):
        self.run_async(
            lambda: self.pc.save(),
            start_msg="Saving advance...",
            success_msg="Progress saved successfully"
        )

    def export_result(self):
        self.run_async(
            lambda: self.pc.export(),
            start_msg="Exporting results...",
            success_msg="Export completed successfully"
        )

    def run(self):
        self.root.mainloop()