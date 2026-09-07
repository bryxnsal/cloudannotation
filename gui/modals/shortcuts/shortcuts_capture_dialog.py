"""
ShortcutsCaptureDialog: Modal popup that listens for keystrokes, including combinations
(e.g., Ctrl+Z, Ctrl+Shift+A, Alt+O, or single keys like Q, 1).
"""
import tkinter as tk
from tkinter import ttk, messagebox
from gui.theme import COLORS
from gui.services.shortcut_manager import normalize_combo_string


def event_to_combo(event) -> str:
    """Parse Tkinter KeyEvent into a normalized combo string: e.g. 'ctrl+z', 'ctrl+shift+a'."""
    mods = []
    # state bitmasks on X11 / Tkinter: 0x4=Control, 0x1=Shift, 0x8 or 0x80=Alt/Mod1
    state = event.state
    if state & 0x4:
        mods.append('ctrl')
    if state & 0x1:
        mods.append('shift')
    if (state & 0x8) or (state & 0x80):
        mods.append('alt')

    keysym = event.keysym.lower()
    # Ignore standalone modifier presses
    if keysym in ('control_l', 'control_r', 'shift_l', 'shift_r', 'alt_l', 'alt_r', 'meta_l', 'meta_r'):
        return ""

    if keysym.startswith('kp_') and len(keysym) == 4 and keysym[3].isdigit():
        keysym = keysym[3]

    parts = mods + [keysym]
    return normalize_combo_string("+".join(parts))


class ShortcutsCaptureDialog(tk.Toplevel):
    """
    Mini dialog that captures the next pressed key or key combination to assign as shortcut.
    """
    def __init__(self, parent, target_title, current_key, existing_mapping, item_type="Class"):
        super().__init__(parent)
        self.target_title = target_title
        self.current_key = current_key
        self.existing_mapping = dict(existing_mapping) # {key: title}
        self.item_type = item_type
        self.result_key = None

        self.title("Assign Shortcut")
        self.geometry("420x200")
        self.resizable(False, False)
        self.configure(bg=COLORS['bg_primary'])

        self._setup_ui()
        self.bind("<Key>", self._on_key_pressed)

        self.transient(parent)
        self.update_idletasks()
        try:
            self.grab_set()
        except Exception:
            pass
        self.focus_force()

    def _setup_ui(self):
        frame = ttk.Frame(self, style='Modern.TFrame', padding=16)
        frame.pack(fill='both', expand=True)

        lbl1 = ttk.Label(
            frame,
            text="Assign Shortcut for {}:".format(self.item_type),
            style='Modern.TLabel',
            font=('Segoe UI', 10)
        )
        lbl1.pack(pady=(0, 4))

        lbl_class = ttk.Label(
            frame,
            text="{}".format(self.target_title),
            style='Title.TLabel',
            font=('Segoe UI', 12, 'bold')
        )
        lbl_class.pack(pady=(0, 10))

        self.hint_lbl = ttk.Label(
            frame,
            text="Press key or combination (e.g. Ctrl+Z, Ctrl+Shift+A, Q, 1)...\n(Press Escape to cancel, or click Clear Key)",
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
        # Escape cancels the dialog
        if event.keysym == "Escape" and not (event.state & 0x4 or event.state & 0x1 or event.state & 0x8):
            self.destroy()
            return

        combo = event_to_combo(event)
        if not combo:
            return

        # Check for conflict
        existing_owner = self.existing_mapping.get(combo)
        if existing_owner and existing_owner != self.target_title:
            confirm = messagebox.askyesno(
                "Shortcut Conflict",
                "Combination '[ {} ]' is currently assigned to:\n'{}'\n\n"
                "Do you want to reassign it to '{}'?\n"
                "(The previous item will lose this shortcut)".format(
                    combo.upper(), existing_owner, self.target_title
                ),
                parent=self
            )
            if not confirm:
                return

        self.result_key = combo
        self.destroy()
