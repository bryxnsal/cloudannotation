"""
ShortcutManager: Service responsible for managing, persisting, and binding classification shortcuts.
Decoupled from GUI views. Persists configuration to shortcuts_config.json.
"""
import os
import json
import Config

CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'shortcuts_config.json')

# Default natural mapping based on Config.labels order
DEFAULT_KEYS = [
    '1', '2', '3', '4', '5', '6', '7', '8', '9', '0',
    'q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p',
    'a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l'
]

class ShortcutManager:
    """
    Manages key-to-class bindings, persistence, and Tkinter event listeners.
    """
    def __init__(self, config_path=CONFIG_FILE):
        self.config_path = config_path
        self.enabled = True
        self.key_to_class = {}   # e.g. {'1': 'Suelo', '2': 'Vegetación'}
        self.class_to_key = {}   # e.g. {'Suelo': '1', 'Vegetación': '2'}
        self.bound_keys = set()
        self.load_config()

    def get_default_mapping(self):
        """Generate default mapping matching Config.labels."""
        key_map = {}
        # Order: 1-9 for main classes, 0 for No clasificado, letters for subsequent
        labels_list = list(Config.labels.keys())
        # Place 'No clasificado' to '0' if present
        unclassified = "No clasificado"
        other_labels = [l for l in labels_list if l != unclassified]

        key_idx = 0
        for label in other_labels:
            if key_idx < 9:
                key_map[DEFAULT_KEYS[key_idx]] = label
                key_idx += 1
            elif key_idx == 9:
                # 0 is reserved for unclassified if available
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

    def load_config(self):
        """Load shortcuts from JSON or generate defaults."""
        if os.path.isfile(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                    self.enabled = data.get('enabled', True)
                    self.key_to_class = data.get('shortcuts', {})
            except Exception as e:
                print("Error reading shortcuts_config.json, using defaults:", e)
                self.key_to_class = self.get_default_mapping()
                self.enabled = True
        else:
            self.key_to_class = self.get_default_mapping()
            self.enabled = True
            self.save_config()

        self._rebuild_class_to_key()

    def _rebuild_class_to_key(self):
        self.class_to_key = {cls_name: key for key, cls_name in self.key_to_class.items()}

    def save_config(self):
        """Save current configuration to JSON file."""
        data = {
            'enabled': self.enabled,
            'shortcuts': self.key_to_class
        }
        try:
            with open(self.config_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print("Error saving shortcuts_config.json:", e)

    def set_mapping(self, new_key_to_class, enabled=True):
        """Update mapping in-memory and persist."""
        self.key_to_class = dict(new_key_to_class)
        self.enabled = enabled
        self._rebuild_class_to_key()
        self.save_config()

    def reset_to_defaults(self):
        """Reset to factory default mapping."""
        self.key_to_class = self.get_default_mapping()
        self.enabled = True
        self._rebuild_class_to_key()
        self.save_config()

    def clear_all_shortcuts(self):
        """Clear all shortcuts (disable all bindings)."""
        self.key_to_class = {}
        self.class_to_key = {}
        self.save_config()

    def get_key_for_class(self, class_name):
        return self.class_to_key.get(class_name, None)

    def get_class_for_key(self, key):
        if not self.enabled:
            return None
        return self.key_to_class.get(key.lower(), None)

    def apply_bindings(self, root, on_shortcut_callback):
        """
        Dynamically bind/unbind keys on the Tkinter root window.
        """
        # Unbind previous keys
        for k in list(self.bound_keys):
            try:
                root.unbind("<Key-{}>".format(k))
                root.unbind("<Key-{}>".format(k.upper()))
                if k.isdigit():
                    root.unbind("<KP_{}>".format(k))
            except Exception:
                pass
        self.bound_keys.clear()

        if not self.enabled:
            return

        # Bind new keys
        for key, class_name in self.key_to_class.items():
            k_lower = key.lower()

            def make_handler(c_name=class_name, key_pressed=k_lower):
                def handler(event):
                    # Ignore if user is typing in a text entry or combobox
                    widget = event.widget
                    w_class = widget.winfo_class()
                    if w_class in ('Entry', 'Text', 'TCombobox'):
                        return
                    on_shortcut_callback(c_name, key_pressed)
                return handler

            # Standard key
            root.bind("<Key-{}>".format(k_lower), make_handler())
            root.bind("<Key-{}>".format(k_lower.upper()), make_handler())
            self.bound_keys.add(k_lower)

            # Keypad equivalent if digit
            if k_lower.isdigit():
                root.bind("<KP_{}>".format(k_lower), make_handler())
                self.bound_keys.add("KP_{}".format(k_lower))
