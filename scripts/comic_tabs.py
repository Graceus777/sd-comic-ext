"""
Comic Generator — A1111 WebUI Extension entry point.

Registers the Comic Generator tab:
  - Comic — JSON-scripted panel generation + page assembly
  - Assembly — standalone page re-assembly + PDF/CBZ export

Strip scripts are available as built-in examples in the Comic tab's
"Load script file" dropdown, or by loading any saved script JSON.
"""
import os
import sys

# Get the path to 'sd-comic-ext' (one level up from this script)
extension_root = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

# Inject it into sys.path so 'import comic' works
if extension_root not in sys.path:
    sys.path.append(extension_root)

# Now your original import will work
from comic.ui_comic import create_comic_tab

# Ensure the extension's package is importable
ext_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ext_dir not in sys.path:
    sys.path.insert(0, ext_dir)

from modules import script_callbacks


def on_ui_tabs():
    from comic.ui_comic import create_comic_tab
    return [create_comic_tab()]


script_callbacks.on_ui_tabs(on_ui_tabs)
