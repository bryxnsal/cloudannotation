import tkinter as tk
from tkinter import ttk
import datetime
import Config
from PointCloud import PointCloud

class ModernAnnotationGUI:
    def __init__(self, pc: PointCloud):
        self.root = tk.Tk()
        self.root.title("Point Cloud Annotator")
        self.root.geometry("450x380")
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
        self.overwrite_var = tk.BooleanVar(self.root)
        self.show_logs = tk.BooleanVar(self.root, False)  # Logs hidden by default

        # Status tracking
        self.status_messages = []

        # Build GUI
        self._create_widgets()
        
        # Add initial log message
        self.log_message("System initialized", "INFO")

    def setup_styles(self):
        """Configure modern ttk styles."""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure colors
        style.configure('Modern.TFrame', background=self.colors['bg_secondary'])
        style.configure('Accent.TFrame', background=self.colors['bg_accent'])
        style.configure('Modern.TLabel', background=self.colors['bg_secondary'], 
                       foreground=self.colors['text_primary'], font=('Segoe UI', 8))
        style.configure('Title.TLabel', background=self.colors['bg_secondary'], 
                       foreground=self.colors['text_primary'], font=('Segoe UI', 9, 'bold'))
        style.configure('Modern.TButton', font=('Segoe UI', 8))
        style.configure('Accent.TButton', font=('Segoe UI', 8, 'bold'))

    def _create_widgets(self):
        """Create modern GUI layout."""
        # Main container
        main_frame = ttk.Frame(self.root, style='Modern.TFrame')
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Control sections
        self._create_classification_section(main_frame)
        self._create_rendering_section(main_frame)
        self._create_save_export_section(main_frame)

        # Compact status at bottom
        self._create_status_section(main_frame)

    def _create_classification_section(self, parent):
        """Create compact classification section."""
        section_frame = ttk.LabelFrame(parent, text=" [CLASS] ", 
                                     style='Modern.TFrame', padding=8)
        section_frame.pack(fill='x', pady=(0, 6))

        # Compact layout - class selection and execute in one row
        top_row = ttk.Frame(section_frame, style='Modern.TFrame')
        top_row.pack(fill='x', pady=(0, 6))
        
        self.class_combo = ttk.Combobox(top_row, textvariable=self.option_var, 
                                       values=list(Config.labels.keys()), 
                                       state='readonly', width=12, font=('Segoe UI', 8))
        self.class_combo.pack(side='left', fill='x', expand=True, padx=(0, 4))

        ttk.Button(top_row, text="Execute", 
                  command=self.execute_selection).pack(side='right')

        # Overwrite checkbox - compact
        ttk.Checkbutton(section_frame, text="Overwrite", 
                       variable=self.overwrite_var).pack(anchor='w')

    def _create_rendering_section(self, parent):
        """Create compact rendering section."""
        section_frame = ttk.LabelFrame(parent, text=" [RENDER] ", 
                                     style='Modern.TFrame', padding=8)
        section_frame.pack(fill='x', pady=(0, 6))

        # Render buttons in one row
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

        # Compact listbox
        self.label_listbox = tk.Listbox(section_frame, selectmode=tk.MULTIPLE, 
                                       height=3, bg=self.colors['bg_accent'], 
                                       fg=self.colors['text_primary'],
                                       selectbackground=self.colors['accent'],
                                       font=('Segoe UI', 7), borderwidth=1, relief='solid')
        self.label_listbox.pack(fill='x', pady=(0, 4))

        # Populate listbox
        for label in Config.labels.keys():
            self.label_listbox.insert(tk.END, label)

        # Select all button
        ttk.Button(section_frame, text="Select All", 
                  command=self.select_all_labels).pack(fill='x')

    def _create_save_export_section(self, parent):
        """Create compact save/export section."""
        section_frame = ttk.LabelFrame(parent, text=" [I/O] ", 
                                     style='Modern.TFrame', padding=8)
        section_frame.pack(fill='x', pady=(0, 6))

        button_row = ttk.Frame(section_frame, style='Modern.TFrame')
        button_row.pack(fill='x')
        
        ttk.Button(button_row, text="Save", 
                  command=self.save_progress).pack(side='left', padx=(0, 4), fill='x', expand=True)
        ttk.Button(button_row, text="Export", 
                  command=self.export_result).pack(side='right', padx=(4, 0), fill='x', expand=True)

    def _create_status_section(self, parent):
        """Create toggleable status section."""
        # Status bar with toggle button
        status_bar = ttk.Frame(parent, style='Accent.TFrame')
        status_bar.pack(fill='x', pady=(6, 0))
        
        # Current status
        self.status_label = ttk.Label(status_bar, text="Ready", 
                                    style='Modern.TLabel', font=('Consolas', 7))
        self.status_label.pack(side='left')
        
        # Toggle logs button
        self.toggle_btn = ttk.Button(status_bar, text="Log", width=3,
                                   command=self.toggle_logs)
        self.toggle_btn.pack(side='right')

        # Collapsible log frame
        self.log_frame = ttk.Frame(parent, style='Accent.TFrame')
        # Don't pack initially - logs hidden by default
        
        self.mini_log = tk.Text(self.log_frame, height=2, 
                              bg=self.colors['bg_primary'], 
                              fg=self.colors['text_secondary'],
                              font=('Consolas', 6), borderwidth=1, relief='solid',
                              wrap='word', state='disabled')
        self.mini_log.pack(fill='x', pady=(3, 0))
        
        # Configure colors
        self.mini_log.tag_configure('OK', foreground=self.colors['success'])
        self.mini_log.tag_configure('WARN', foreground=self.colors['warning'])
        self.mini_log.tag_configure('ERR', foreground=self.colors['error'])

    def toggle_logs(self):
        """Show/hide log section."""
        if self.show_logs.get():
            # Hide logs
            self.log_frame.pack_forget()
            self.toggle_btn.configure(text="Log")
            self.show_logs.set(False)
            # Resize window smaller
            self.root.geometry("450x350")
        else:
            # Show logs
            self.log_frame.pack(fill='x', pady=(3, 0))
            self.toggle_btn.configure(text="Hide")
            self.show_logs.set(True)
            # Resize window larger
            self.root.geometry("450x420")

    def log_message(self, message, level="INFO"):
        """Add compact message with optional log display."""
        timestamp = datetime.datetime.now().strftime("%H:%M")
        
        # Update status bar
        status_colors = {
            'INFO': self.colors['text_primary'],
            'SUCCESS': self.colors['success'], 
            'WARNING': self.colors['warning'],
            'ERROR': self.colors['error']
        }
        self.status_label.configure(text=f"{timestamp} {message}", 
                                  foreground=status_colors.get(level, self.colors['text_primary']))
        
        # Add to mini log only if visible
        if self.show_logs.get():
            self.mini_log.config(state='normal')
            
            level_map = {'INFO': 'OK', 'SUCCESS': 'OK', 'WARNING': 'WARN', 'ERROR': 'ERR'}
            short_level = level_map.get(level, 'OK')
            
            entry = f"{timestamp} {short_level}: {message}\n"
            self.mini_log.insert('end', entry, short_level)
            
            # Keep only last 2 lines
            lines = self.mini_log.get('1.0', 'end').strip().split('\n')
            if len(lines) > 2:
                self.mini_log.delete('1.0', 'end')
                for line in lines[-2:]:
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
        
        if not selected_option:
            self.log_message("No classification option selected", "WARNING")
            return
            
        try:
            label_value = Config.labels[selected_option]
            self.log_message(f"Executing classification: {selected_option} (Label {label_value})", "INFO")
            self.pc.classify(label_value, overwrite=overwrite)
            self.log_message(f"Classification completed successfully", "SUCCESS")
            if overwrite:
                self.log_message("Existing classifications were overwritten", "INFO")
        except Exception as e:
            self.log_message(f"Classification failed: {str(e)}", "ERROR")

    # ------------------ Rendering Methods ------------------
    def render_all(self):
        try:
            self.log_message("Rendering entire point cloud...", "INFO")
            self.pc.render()
            self.log_message("Point cloud rendered successfully", "SUCCESS")
        except Exception as e:
            self.log_message(f"Rendering failed: {str(e)}", "ERROR")

    def render_selection(self):
        try:
            self.pc.render(highlighted=True)
            self.log_message(f"Selection rendered successfully", "SUCCESS")
        except Exception as e:
            self.log_message(f"Selection rendering failed: {str(e)}", "ERROR")

    def render_selection_inv(self):
        try:
            self.pc.render(highlighted=True, invert=True)
            self.log_message(f"Selection rendered successfully", "SUCCESS")
        except Exception as e:
            self.log_message(f"Selection rendering failed: {str(e)}", "ERROR")

    def render_selected_labels(self):
        selected_indices = self.label_listbox.curselection()
        if not selected_indices:
            self.log_message("No labels selected for rendering", "WARNING")
            return
            
        try:
            # Remove prefix from labels if any
            selected_labels = []
            for i in selected_indices:
                label_text = self.label_listbox.get(i)
                selected_labels.append(Config.labels[label_text])
            
            self.log_message(f"Rendering {len(selected_labels)} selected labels", "INFO")
            self.pc.renderLabel(selected_labels)
            self.log_message(f"Multi-label rendering completed", "SUCCESS")
        except Exception as e:
            self.log_message(f"Multi-label rendering failed: {str(e)}", "ERROR")

    def select_all_labels(self):
        self.label_listbox.select_set(0, tk.END)
        count = self.label_listbox.size()
        self.log_message(f"Selected all {count} labels", "INFO")

    # ------------------ Save / Export Methods ------------------
    def save_progress(self):
        """Save progress with proper logging."""
        try:
            self.log_message("Saving progress...", "INFO")
            self.pc.save()
            self.log_message("Progress saved successfully", "SUCCESS")
        except Exception as e:
            self.log_message(f"Save failed: {str(e)}", "ERROR")

    def export_result(self):
        """Export result with proper logging."""
        try:
            self.log_message("Exporting results...", "INFO")
            self.pc.export()
            self.log_message("Export completed successfully", "SUCCESS")
        except Exception as e:
            self.log_message(f"Export failed: {str(e)}", "ERROR")

    def run(self):
        self.root.mainloop()