"""
ShortcutsCaptureDialog: Modal popup that listens for a single keystroke.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from gui.theme import COLORS

class ShortcutsCaptureDialog(tk.Toplevel):
    """
    Mini dialog that captures the next pressed key to assign as shortcut.
    """
    def __init__(self, parent, class_name, current_key, existing_mapping):
        super().__init__(parent)
        self.class_name = class_name
        self.current_key = current_key
        self.existing_mapping = dict(existing_mapping) # {key: class_name}
        self.result_key = None

        self.title("Assign Shortcut")
        self.geometry("380x180")
        self.resizable(False, False)
        self.configure(bg=COLORS['bg_primary'])

        self.transient(parent)
        self.grab_set()

        self._setup_ui()
        self.bind("<Key>", self._on_key_pressed)
        self.focus_force()

    def _setup_ui(self):
        frame = ttk.Frame(self, style='Modern.TFrame', padding=16)
        frame.pack(fill='both', expand=True)

        lbl1 = ttk.Label(
            frame,
            text="Assign Shortcut for Class:",
            style='Modern.TLabel',
            font=('Segoe UI', 10)
        )
        lbl1.pack(pady=(0, 4))

        lbl_class = ttk.Label(
            frame,
            text="{}".format(self.class_name),
            style='Title.TLabel',
            font=('Segoe UI', 12, 'bold')
        )
        lbl_class.pack(pady=(0, 10))

        self.hint_lbl = ttk.Label(
            frame,
            text="Press any alphanumeric key (0-9, A-Z) on your keyboard...\n(Or press Escape to cancel)",
            style='Modern.TLabel',
            font=('Segoe UI', 9)
        )
        self.hint_lbl.pack(pady=(0, 12))

        btn_row = ttk.Frame(frame, style='Modern.TFrame')
        btn_row.pack(fill='x')

        ttk.Button(
            btn_row,
            text="Clear Key",
            command=self._clear_key
        ).pack(side='left')

        ttk.Button(
            btn_row,
            text="Cancel",
            command=self.destroy
        ).pack(side='right')

    def _clear_key(self):
        self.result_key = ""
        self.destroy()

    def _on_key_pressed(self, event):
        key = event.char
        if not key:
            # Check keysym for digits on keypad or other keys
            keysym = event.keysym
            if keysym.startswith("KP_") and len(keysym) == 4 and keysym[3].isdigit():
                key = keysym[3]
            elif keysym == "Escape":
                self.destroy()
                return
            else:
                return

        if key == "\x1b":  # Escape
            self.destroy()
            return

        key = key.lower()
        if not (key.isalnum() and len(key) == 1):
            return

        # Check for conflict
        existing_class = self.existing_mapping.get(key)
        if existing_class and existing_class != self.class_name:
            confirm = messagebox.askyesno(
                "Shortcut Conflict",
                "Key '[ {} ]' is currently assigned to:\n'{}'\n\n"
                "Do you want to reassign it to '{}'?\n"
                "(The previous class will lose this shortcut)".format(
                    key.upper(), existing_class, self.class_name
                ),
                parent=self
            )
            if not confirm:
                return

        self.result_key = key
        self.destroy()
