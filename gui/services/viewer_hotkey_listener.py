"""
ViewerHotkeyListener: Background keyboard listener that captures classification shortcuts
when the user is interacting inside the 3D viewer window (PPTK or Open3D) or the main GUI window.

Context-Aware:
- Only triggers when the active window is PPTK, Open3D, or the CloudAnnotation GUI.
- Respects PPTK's native camera views (1-9):
  If 1-9 is pressed without point selection, PPTK rotates the camera.
  If 1-9 is pressed WITH point selection, or if letters (q, w, e...) / Numpad keys are pressed,
  classification is executed immediately.
"""
import os
import sys
import subprocess
import threading
from typing import Callable, Optional

try:
    from pynput import keyboard
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False


class ViewerHotkeyListener:
    """
    Listens globally for keyboard shortcuts and filters them based on the active X11 window.
    """
    def __init__(self, pc, shortcut_manager, on_trigger: Callable[[str, str], None], root=None):
        self.pc = pc
        self.shortcut_manager = shortcut_manager
        self.on_trigger = on_trigger
        self.root = root  # Tkinter root for thread-safe dispatching
        self._listener = None
        self._running = False
        self._lock = threading.Lock()

    def start(self):
        """Start listener in background thread if pynput is available."""
        if not PYNPUT_AVAILABLE or self._running:
            return

        self._running = True
        try:
            self._listener = keyboard.Listener(on_press=self._on_press)
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
        """Convert pynput Key / KeyCode into standard character string."""
        if hasattr(key, 'char') and key.char is not None:
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

        return None

    def _on_press(self, key):
        """Callback invoked when a key is pressed anywhere on the system."""
        if not self.shortcut_manager or not self.shortcut_manager.enabled:
            return

        char_key = self._normalize_key(key)
        if not char_key:
            return

        class_name = self.shortcut_manager.get_class_for_key(char_key)
        if not class_name:
            return

        # Check if the currently focused window belongs to CloudAnnotation
        if not self._is_cloudannotation_window_focused():
            return

        # Check PPTK conflict rule:
        # If active window is PPTK and key is 1-9:
        # If there are NO selected points, let PPTK handle it (camera view).
        # If there ARE selected points, or if key is not a digit (e.g. letters q, w, e), classify immediately!
        is_pptk = (getattr(self.pc, 'viewer_type', 'pptk') == 'pptk')
        has_sel = self.pc.has_selection() if self.pc else False

        if is_pptk and char_key.isdigit() and char_key != '0' and not has_sel:
            # Let PPTK rotate camera view without intercepting as classification
            return

        # Dispatch execution safely to Tkinter event loop
        def dispatch():
            try:
                self.on_trigger(class_name, char_key)
            except Exception as e:
                print("Error executing hotkey dispatch:", e)

        if self.root:
            self.root.after_idle(dispatch)
        else:
            threading.Thread(target=dispatch, daemon=True).start()
