"""
ShortcutManager: Service responsible for managing, persisting, and binding shortcuts.
Supports both classification shortcuts and action shortcuts (e.g. All, Select, Open PLY, etc.)
with multi-key combos (e.g. ctrl+z, ctrl+shift+s, alt+o, or single keys).
Persists configuration to ~/.cloudannotation/shortcuts_config.json.
"""
import os
import json
import Config

CONFIG_DIR = os.path.expanduser('~/.cloudannotation')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'shortcuts_config.json')
LEGACY_CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'shortcuts_config.json')

# Recognized global actions
ACTION_DEFINITIONS = [
    ("undo", "Undo Classification (Ctrl+Z)", "Ctrl+Z"),
    ("redo", "Redo Classification (Ctrl+Y)", "Ctrl+Y"),
    ("render_all", "All (Render Full Cloud)", None),
    ("toggle_select", "Select (Work Area / ROI)", None),
    ("select_inv", "Select Inv (Invert Selection)", None),
    ("multi_render", "Multi (Render Selected Labels)", None),
    ("select_all_labels", "Select All Labels", None),
    ("clear_selections", "Clear Selections", None),
    ("open_ply", "Open PLY File", None),
    ("save_advance", "Save Advance", None),
    ("export_result", "Export Result", None),
    ("advances_list", "Advances List Modal", None),
    ("toggle_logs", "Logs (Toggle Mini-log)", None),
    ("toggle_overwrite", "Overwrite (Toggle Checkbox)", None),
    ("open_shortcuts", "Shortcuts Button (Open Modal)", None),
]

DEFAULT_KEYS = [
    '1', '2', '3', '4', '5', '6', '7', '8', '9', '0',
    'q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p',
    'a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l'
]


def normalize_combo_string(combo_str: str) -> str:
    """
    Standardize combo string into lowercase sorted modifiers + key:
    e.g. 'ctrl+shift+a', 'Ctrl + Z' -> 'ctrl+shift+z'
    """
    if not combo_str:
        return ""
    parts = [p.strip().lower() for p in combo_str.split('+') if p.strip()]
    modifiers = []
    key = None
    for p in parts:
        if p in ('ctrl', 'control'):
            if 'ctrl' not in modifiers:
                modifiers.append('ctrl')
        elif p in ('shift',):
            if 'shift' not in modifiers:
                modifiers.append('shift')
        elif p in ('alt',):
            if 'alt' not in modifiers:
                modifiers.append('alt')
        else:
            key = p

    order = {'ctrl': 1, 'shift': 2, 'alt': 3}
    modifiers.sort(key=lambda m: order.get(m, 9))

    if key is None:
        return ""
    if modifiers:
        return "+".join(modifiers) + "+" + key
    return key


class ShortcutManager:
    """
    Manages key-to-class and key-to-action bindings, persistence, and Tkinter listeners.
    """
    def __init__(self, config_path=CONFIG_FILE):
        self.config_path = config_path
        self.enabled = True
        self.key_to_class = {}    # e.g. {'1': 'Suelo', 'w': 'Vegetación'}
        self.class_to_key = {}    # e.g. {'Suelo': '1'}
        self.action_shortcuts = {} # e.g. {'render_all': 'ctrl+a', 'undo': 'ctrl+z'}
        self.key_to_action = {}   # e.g. {'ctrl+a': 'render_all', 'ctrl+z': 'undo'}
        self.bound_keys = set()
        self.load_config()

    def get_default_classification_mapping(self):
        """Generate default mapping matching Config.labels."""
        key_map = {}
        labels_list = list(Config.labels.keys())
        unclassified = "No clasificado"
        other_labels = [l for l in labels_list if l != unclassified]

        key_idx = 0
        for label in other_labels:
            if key_idx < 9:
                key_map[DEFAULT_KEYS[key_idx]] = label
                key_idx += 1
            elif key_idx == 9:
                key_idx += 1
                key_map[DEFAULT_KEYS[key_idx]] = label
                key_idx += 1
            else:
                if key_idx < len(DEFAULT_KEYS):
                    key_map[DEFAULT_KEYS[key_idx]] = label
                    key_idx += 1

        if unclassified in labels_list:
            key_map['0'] = unclassified

        return key_map

    def get_default_action_shortcuts(self):
        """Generate default mapping for actions (empty by default as requested, with standard ctrl+z/ctrl+y)."""
        actions = {}
        for action_id, _, default_combo in ACTION_DEFINITIONS:
            if default_combo:
                actions[action_id] = normalize_combo_string(default_combo)
        return actions

    def load_config(self):
        """Load shortcuts from JSON or generate defaults, migrating legacy config if present."""
        if not os.path.isfile(self.config_path) and os.path.isfile(LEGACY_CONFIG_FILE):
            try:
                os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
                with open(LEGACY_CONFIG_FILE, 'r') as f_old:
                    legacy_data = json.load(f_old)
                with open(self.config_path, 'w') as f_new:
                    json.dump(legacy_data, f_new, indent=2)
            except Exception as e:
                print("Notice: Error migrating legacy shortcuts_config.json:", e)

        if os.path.isfile(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                    self.enabled = data.get('enabled', True)
                    raw_classes = data.get('shortcuts', {})
                    self.key_to_class = {normalize_combo_string(k): v for k, v in raw_classes.items() if k}
                    raw_actions = data.get('actions', {})
                    self.action_shortcuts = {a: normalize_combo_string(k) for a, k in raw_actions.items() if k}
                    # Initialize all recognized actions from ACTION_DEFINITIONS
                    for act_id, _, default_combo in ACTION_DEFINITIONS:
                        if act_id not in self.action_shortcuts:
                            self.action_shortcuts[act_id] = normalize_combo_string(default_combo) if default_combo else None
            except Exception as e:
                print("Error reading shortcuts_config.json, using defaults:", e)
                self.key_to_class = self.get_default_classification_mapping()
                self.action_shortcuts = self.get_default_action_shortcuts()
                self.enabled = True
        else:
            self.key_to_class = self.get_default_classification_mapping()
            self.action_shortcuts = self.get_default_action_shortcuts()
            self.enabled = True
            self.save_config()

        self._rebuild_lookups()

    def _rebuild_lookups(self):
        self.class_to_key = {cls_name: key for key, cls_name in self.key_to_class.items()}
        self.key_to_action = {key: act for act, key in self.action_shortcuts.items() if key}

    def save_config(self):
        """Save current configuration to ~/.cloudannotation/shortcuts_config.json."""
        data = {
            'enabled': self.enabled,
            'shortcuts': self.key_to_class,
            'actions': self.action_shortcuts
        }
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print("Error saving shortcuts_config.json:", e)

    def set_mapping(self, new_key_to_class, new_action_shortcuts=None, enabled=True):
        """Update mapping in-memory and persist."""
        self.key_to_class = {normalize_combo_string(k): v for k, v in new_key_to_class.items() if k}
        if new_action_shortcuts is not None:
            self.action_shortcuts = {a: normalize_combo_string(k) for a, k in new_action_shortcuts.items() if k}
        self.enabled = enabled
        self._rebuild_lookups()
        self.save_config()

    def reset_to_defaults(self):
        """Reset to factory default mapping."""
        self.key_to_class = self.get_default_classification_mapping()
        self.action_shortcuts = self.get_default_action_shortcuts()
        self.enabled = True
        self._rebuild_lookups()
        self.save_config()

    def clear_all_shortcuts(self):
        """Clear all shortcuts (disable all bindings)."""
        self.key_to_class = {}
        self.class_to_key = {}
        self.action_shortcuts = {}
        self.key_to_action = {}
        self.save_config()

    def get_key_for_class(self, class_name):
        return self.class_to_key.get(class_name, None)

    def get_class_for_key(self, key):
        if not self.enabled:
            return None
        norm = normalize_combo_string(key)
        return self.key_to_class.get(norm, None)

    def get_action_for_key(self, key):
        norm = normalize_combo_string(key)
        return self.key_to_action.get(norm, None)

    def get_key_for_action(self, action_id):
        return self.action_shortcuts.get(action_id, None)

    def apply_bindings(self, root, on_classification_callback, on_action_callback=None):
        """
        Dynamically bind/unbind keys across all window widgets.
        Supports single keys, ctrl+key, ctrl+shift+key, alt+key, etc.
        """
        for seq in list(self.bound_keys):
            try:
                root.unbind_all(seq)
            except Exception:
                pass
        self.bound_keys.clear()

        if not self.enabled:
            return

        def parse_to_tk_sequence(combo_str):
            """Convert normalized combo 'ctrl+shift+a' to Tk sequence '<Control-Shift-Key-a>'."""
            parts = combo_str.split('+')
            key = parts[-1]
            mods = parts[:-1]
            tk_mods = []
            for m in mods:
                if m == 'ctrl':
                    tk_mods.append('Control')
                elif m == 'shift':
                    tk_mods.append('Shift')
                elif m == 'alt':
                    tk_mods.append('Alt')
            mod_prefix = "-".join(tk_mods)
            if mod_prefix:
                return "<{}-Key-{}>".format(mod_prefix, key)
            return "<Key-{}>".format(key)

        # 1. Bind classification shortcuts
        for combo, class_name in self.key_to_class.items():
            tk_seq = parse_to_tk_sequence(combo)

            def make_class_handler(c_name=class_name, c_combo=combo):
                def handler(event):
                    widget = event.widget
                    try:
                        if widget.winfo_toplevel() != root:
                            return
                    except Exception:
                        pass
                    try:
                        w_class = widget.winfo_class()
                        if w_class in ('Entry', 'TEntry', 'Text'):
                            return
                    except Exception:
                        pass
                    on_classification_callback(c_name, c_combo)
                    return "break"
                return handler

            try:
                root.bind_all(tk_seq, make_class_handler())
                self.bound_keys.add(tk_seq)
                # If single letter/digit, also bind uppercase/keypad
                if '+' not in combo:
                    root.bind_all("<Key-{}>".format(combo.upper()), make_class_handler())
                    self.bound_keys.add("<Key-{}>".format(combo.upper()))
                    if combo.isdigit():
                        root.bind_all("<KP_{}>".format(combo), make_class_handler())
                        self.bound_keys.add("<KP_{}>".format(combo))
            except Exception as e:
                print("Error binding sequence {}: {}".format(tk_seq, e))

        # 2. Bind action shortcuts
        if on_action_callback:
            for action_id, combo in self.action_shortcuts.items():
                if not combo:
                    continue
                tk_seq = parse_to_tk_sequence(combo)

                def make_action_handler(act=action_id, c_combo=combo):
                    def handler(event):
                        widget = event.widget
                        try:
                            if widget.winfo_toplevel() != root:
                                return
                        except Exception:
                            pass
                        try:
                            w_class = widget.winfo_class()
                            if w_class in ('Entry', 'TEntry', 'Text'):
                                return
                        except Exception:
                            pass
                        on_action_callback(act, c_combo)
                        return "break"
                    return handler

                try:
                    root.bind_all(tk_seq, make_action_handler())
                    self.bound_keys.add(tk_seq)
                    if '+' not in combo:
                        root.bind_all("<Key-{}>".format(combo.upper()), make_action_handler())
                        self.bound_keys.add("<Key-{}>".format(combo.upper()))
                        if combo.isdigit():
                            root.bind_all("<KP_{}>".format(combo), make_action_handler())
                            self.bound_keys.add("<KP_{}>".format(combo))
                except Exception as e:
                    print("Error binding action sequence {}: {}".format(tk_seq, e))
