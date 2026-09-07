"""
StatusBarView: Component for the bottom status, progress bar and collapsible mini log.
Provides fluid progress bar animations and categorized real-time logging.
"""
import datetime
import tkinter as tk
from tkinter import ttk
from gui.components.base_component import BaseComponent

class StatusBarView(BaseComponent):
    """
    Bottom bar with determinate/indeterminate progress indicator, timestamped status, and log panel.
    """
    def __init__(self, parent, app, pc, **kwargs):
        super().__init__(parent, app, pc, **kwargs)
        self.show_logs = tk.BooleanVar(self, value=False)
        self._create_widgets()

    def _create_widgets(self):
        # 1. Progress Bar
        progress_frame = ttk.Frame(self, style='Modern.TFrame')
        progress_frame.pack(fill='x', pady=(4, 4))

        self.progress_bar = ttk.Progressbar(
            progress_frame,
            orient='horizontal',
            mode='determinate',
            maximum=100,
            value=0,
            style='Modern.Horizontal.TProgressbar'
        )
        self.progress_bar.pack(fill='x', expand=True, ipady=1)

        # 2. Status bar with toggle button
        status_bar = ttk.Frame(self, style='Accent.TFrame')
        status_bar.pack(fill='x', pady=(2, 0))

        self.status_label = ttk.Label(
            status_bar,
            text="Ready",
            style='Modern.TLabel',
            font=('Consolas', 9)
        )
        self.status_label.pack(side='left', padx=4, pady=2)

        self.toggle_btn = ttk.Button(
            status_bar,
            text="Log",
            width=5,
            command=self.toggle_logs
        )
        self.toggle_btn.pack(side='right', padx=2, pady=2)

        # 3. Collapsible log frame with scrollbar
        self.log_frame = ttk.Frame(self, style='Modern.TFrame')

        log_scroll = ttk.Scrollbar(self.log_frame)
        log_scroll.pack(side='right', fill='y')

        self.mini_log = tk.Text(
            self.log_frame,
            height=5,
            bg=self.colors['bg_primary'],
            fg=self.colors['text_secondary'],
            font=('Consolas', 9),
            borderwidth=1,
            relief='solid',
            wrap='word',
            state='disabled',
            yscrollcommand=log_scroll.set
        )
        self.mini_log.pack(side='left', fill='both', expand=True, pady=(3, 0))
        log_scroll.config(command=self.mini_log.yview)

        # Color tags
        self.mini_log.tag_configure('OK', foreground=self.colors['success'])
        self.mini_log.tag_configure('WARN', foreground=self.colors['warning'])
        self.mini_log.tag_configure('ERR', foreground=self.colors['error'])

    def start_progress(self, message=None):
        """Start smooth indeterminate progress animation."""
        if message:
            self.log_message(message, "INFO")
        self.progress_bar.config(mode='indeterminate')
        self.progress_bar.start(10)
        self.update_idletasks()

    def stop_progress(self, message=None, level="SUCCESS"):
        """Stop progress animation and reset value to 0."""
        self.progress_bar.stop()
        self.progress_bar.config(mode='determinate', value=0)
        if message:
            self.log_message(message, level)
        self.update_idletasks()

    def set_progress(self, value, maximum=100, message=None):
        """Set determinate progress."""
        self.progress_bar.stop()
        self.progress_bar.config(mode='determinate', maximum=maximum, value=value)
        if message:
            self.log_message(message, "INFO")
        self.update_idletasks()

    def toggle_logs(self):
        """Show or hide log panel."""
        if self.show_logs.get():
            self.log_frame.pack_forget()
            self.toggle_btn.configure(text="Log")
            self.show_logs.set(False)
            self.app.root.geometry("520x750")
        else:
            self.log_frame.pack(fill='both', expand=True, pady=(3, 0))
            self.toggle_btn.configure(text="Hide")
            self.show_logs.set(True)
            self.app.root.geometry("520x835")

    def log_message(self, message, level="INFO"):
        """Add timestamped message to status label and mini log."""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")

        status_colors = {
            'INFO': self.colors['text_primary'],
            'SUCCESS': self.colors['success'],
            'WARNING': self.colors['warning'],
            'ERROR': self.colors['error']
        }
        self.status_label.configure(
            text="{} {}".format(timestamp, message),
            foreground=status_colors.get(level, self.colors['text_primary'])
        )

        if self.show_logs.get():
            self.mini_log.config(state='normal')
            level_map = {'INFO': 'OK', 'SUCCESS': 'OK', 'WARNING': 'WARN', 'ERROR': 'ERR'}
            short_level = level_map.get(level, 'OK')

            entry = "{} {}: {}\n".format(timestamp, short_level, message)
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
