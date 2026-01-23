import sys
import os

def get_base_path():
    """
    Return the base path of the application.
    If frozen (PyInstaller), returns the directory of the executable.
    Otherwise, returns the current working directory.
    
    This ensures that external data files (DB, images) are always looked for
    relative to the executable location in portable mode.
    """
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return os.path.dirname(sys.executable)
    else:
        # Running as script
        return os.getcwd()

def get_resource_path(relative_path):
    """
    Get absolute path to resource, works for dev and for PyInstaller.
    Use this for bundled resources (icons, static assets inside the exe).
    For external data (DB, user images), use get_base_path() instead.
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.getcwd()
    
    return os.path.join(base_path, relative_path)
