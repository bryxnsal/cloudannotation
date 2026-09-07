"""
ViewerHotkeyListener: Background keyboard listener that captures classification shortcuts,
Ctrl+Z / Ctrl+Y (Undo/Redo), and custom action shortcuts directly while interacting
inside 3D viewer windows (PPTK or Open3D) or the main CloudAnnotation GUI window.

Supports:
- Single keys: e.g. '1', 'q', 'w'
- Key combinations: e.g. 'ctrl+z', 'ctrl+shift+a', 'alt+s'
- Context filtering: ignores keystrokes when working in browser/terminal/external apps.
- PPTK safety: single digits 1-9 rotate camera if no points are selected.
"""
import os
import sys
import subprocess
import threading
from typing import Callable, Optional
from gui.services.shortcut_manager import normalize_combo_string

try:
    from pynput import keyboard
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False


class ViewerHotkeyListener:
    """
    Listens globally for keystrokes and modifier combinations, filtering by focused X11 window.
    """
    def __init__(self, pc, shortcut_manager, on_class_trigger: Callable[[str, str], None],
                 on_action_trigger: Optional[Callable[[str, str], None]] = None, root=None):
        self.pc = pc
        self.shortcut_manager = shortcut_manager
        self.on_class_trigger = on_class_trigger
        self.on_action_trigger = on_action_trigger
        self.root = root  # Tkinter root for thread-safe dispatching
        self._listener = None
        self._running = False
        self._active_modifiers = set()
        self._lock = threading.Lock()

    def start(self):
        """Start listener in background thread if pynput is available."""
        if not PYNPUT_AVAILABLE or self._running:
            return

        self._running = True
        try:
            self._listener = keyboard.Listener(
                on_press=self._on_press,
                on_release=self._on_release
            )
            self._listener.daemon = True
            self._listener.start()
        except Exception as e:
            print("ViewerHotkeyListener: Failed to start listener:", e)
            self._running = False

    def stop(self):
        """Stop keyboard listener."""
        self._running = False
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None

    def _get_active_window_info(self):
        """Query the currently focused X11 window (PID, WM_CLASS, WM_NAME)."""
        if not sys.platform.startswith('linux'):
            return None, "", ""

        try:
            res = subprocess.run(
                ['xprop', '-root', '-notype', '_NET_ACTIVE_WINDOW'],
                capture_output=True, text=True, timeout=0.1
            )
            out = res.stdout.strip()
            if not out or '0x' not in out:
                return None, "", ""
            win_id = out.split()[-1]
            if win_id == '0x0':
                return None, "", ""

            res_props = subprocess.run(
                ['xprop', '-id', win_id, '-notype', '_NET_WM_PID', 'WM_CLASS', 'WM_NAME'],
                capture_output=True, text=True, timeout=0.1
            )
            pid = None
            wm_class = ""
            wm_name = ""
            for line in res_props.stdout.splitlines():
                if line.startswith('_NET_WM_PID'):
                    try:
                        pid = int(line.split('=')[-1].strip())
                    except ValueError:
                        pass
                elif line.startswith('WM_CLASS'):
                    wm_class = line.split('=', 1)[-1].strip().lower()
                elif line.startswith('WM_NAME'):
                    wm_name = line.split('=', 1)[-1].strip().lower()
            return pid, wm_class, wm_name
        except Exception:
            return None, "", ""

    def _is_cloudannotation_window_focused(self) -> bool:
        """
        Check if the active window is:
        1. PPTK viewer window (PID matching pptk subprocess or class 'viewer')
        2. Open3D viewer window (title/class containing 'open3d' or 'cloudannotation - open3d viewer')
        3. Main CloudAnnotation Tkinter GUI window
        """
        pid, wm_class, wm_name = self._get_active_window_info()

        # 1. Check PPTK
        if self.pc and getattr(self.pc, 'viewer_type', 'pptk') == 'pptk':
            pptk_adapter = getattr(self.pc, 'viewer_adapter', None)
            pptk_viewer = getattr(pptk_adapter, 'viewer', None)
            if pptk_viewer and hasattr(pptk_viewer, '_process') and pptk_viewer._process:
                if pid is not None and pid == pptk_viewer._process.pid:
                    return True
            if 'viewer' in wm_class or 'viewer' in wm_name:
                return True

        # 2. Check Open3D
        if 'open3d' in wm_class or 'open3d' in wm_name:
            return True

        # 3. Check Main GUI (Tkinter)
        if 'cloudannotation' in wm_name or 'cloudannotation' in wm_class:
            return True

        current_pid = os.getpid()
        if pid is not None and pid == current_pid:
            return True

        return False

    def _normalize_key(self, key) -> Optional[str]:
        """Extract base key name from pynput event."""
        if hasattr(key, 'char') and key.char is not None:
            # When Ctrl is held, key.char may be control characters (e.g. \x1a for Ctrl+Z)
            code = ord(key.char)
            if 1 <= code <= 26:
                return chr(code + ord('a') - 1)
            return key.char.lower()

        key_str = str(key)
        # Numpad representation in pynput
        if key_str.startswith('<') and key_str.endswith('>'):
            code_val = key_str[1:-1]
            if code_val.isdigit():
                vk = int(code_val)
                if 65456 <= vk <= 65465:
                    return str(vk - 65456)
                if 96 <= vk <= 105:
                    return str(vk - 96)

        # Standard keys like 'esc', 'space', etc.
        if hasattr(key, 'name'):
            return key.name.lower()

        return None

    def _on_release(self, key):
        """Track modifier releases."""
        with self._lock:
            if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
                self._active_modifiers.discard('ctrl')
            elif key in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r):
                self._active_modifiers.discard('shift')
            elif key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r):
                self._active_modifiers.discard('alt')

    def _on_press(self, key):
        """Callback invoked when any key is pressed."""
        # Track modifier presses
        with self._lock:
            if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
                self._active_modifiers.add('ctrl')
                return
            elif key in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r):
                self._active_modifiers.add('shift')
                return
            elif key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r):
                self._active_modifiers.add('alt')
                return

        if not self.shortcut_manager or not self.shortcut_manager.enabled:
            return

        base_key = self._normalize_key(key)
        if not base_key:
            return

        with self._lock:
            mods = sorted(list(self._active_modifiers))

        if mods:
            combo = "+".join(mods) + "+" + base_key
        else:
            combo = base_key

        combo = normalize_combo_string(combo)

        # Check if window belongs to CloudAnnotation or Viewers
        if not self._is_cloudannotation_window_focused():
            return

        # 1. Check if combo matches an ACTION shortcut (e.g. undo 'ctrl+z', redo 'ctrl+y', 'render_all', etc.)
        action_id = self.shortcut_manager.get_action_for_key(combo)
        if action_id and self.on_action_trigger:
            def dispatch_action():
                try:
                    self.on_action_trigger(action_id, combo)
                except Exception as e:
                    print("Error executing action hotkey dispatch:", e)

            if self.root:
                self.root.after_idle(dispatch_action)
            else:
                threading.Thread(target=dispatch_action, daemon=True).start()
            return

        # 2. Check if combo matches a CLASSIFICATION shortcut
        class_name = self.shortcut_manager.get_class_for_key(combo)
        if class_name and self.on_class_trigger:
            # Check PPTK conflict rule:
            # If active window is PPTK and single digit 1-9:
            # If NO points selected, let PPTK rotate camera view.
            is_pptk = (getattr(self.pc, 'viewer_type', 'pptk') == 'pptk')
            has_sel = self.pc.has_selection() if self.pc else False

            if is_pptk and combo.isdigit() and combo != '0' and not has_sel:
                return

            def dispatch_class():
                try:
                    self.on_class_trigger(class_name, combo)
                except Exception as e:
                    print("Error executing classification hotkey dispatch:", e)

            if self.root:
                self.root.after_idle(dispatch_class)
            else:
                threading.Thread(target=dispatch_class, daemon=True).start()
