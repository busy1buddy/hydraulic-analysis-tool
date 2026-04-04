"""
Session Preferences
====================
Save and restore last opened file, window geometry, and UI state.
Stored in ~/.hydraulic_tool/preferences.json.
"""

import os
import json


PREFS_DIR = os.path.join(os.path.expanduser('~'), '.hydraulic_tool')
PREFS_FILE = os.path.join(PREFS_DIR, 'preferences.json')


def load_preferences():
    """Load preferences from disk. Returns empty dict if not found."""
    if os.path.exists(PREFS_FILE):
        try:
            with open(PREFS_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_preferences(prefs):
    """Save preferences dict to disk."""
    os.makedirs(PREFS_DIR, exist_ok=True)
    try:
        with open(PREFS_FILE, 'w') as f:
            json.dump(prefs, f, indent=2)
    except IOError:
        pass


def get_pref(key, default=None):
    """Get a single preference value."""
    return load_preferences().get(key, default)


def set_pref(key, value):
    """Set a single preference value."""
    prefs = load_preferences()
    prefs[key] = value
    save_preferences(prefs)
