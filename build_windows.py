import os
import sys
import shutil
import subprocess

def create_windows_executable():
    """
    Creates a standalone Windows executable using PyInstaller.
    This script should be run on a Windows machine.
    """
    print("=== Warehouse GUI Build Script for Windows ===")
    
    # 1. Check requirements
    try:
        import PyInstaller
    except ImportError:
        print("PyInstaller not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
    
    # 2. Define paths
    base_dir = os.path.dirname(os.path.abspath(__file__))
    dist_dir = os.path.join(base_dir, "dist")
    build_dir = os.path.join(base_dir, "build")
    
    # Clean previous builds
    if os.path.exists(dist_dir):
        shutil.rmtree(dist_dir)
    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)
        
    print("Building executable...")
    
    # 3. Run PyInstaller
    # --onefile: Create a single exe file
    # --windowed: No console window (GUI only)
    # --name: Name of the executable
    # --add-data: Add resource files (if any, e.g. icons) - format: src;dest (Windows)
    # --hidden-import: Explicitly import hidden dependencies
    
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name", "WarehouseGUI",
        "--hidden-import", "sqlalchemy.ext.asyncio",
        "--hidden-import", "sqlalchemy.dialects.sqlite.aiosqlite",
        "--hidden-import", "greenlet",
        "--hidden-import", "aiosqlite",
        "main.py"
    ]
    
    # If you have an icon, uncomment the following line and ensure icon.ico exists
    # cmd.extend(["--icon", "resources/icon.ico"])
    
    subprocess.check_call(cmd)
    
    print("\n=== Build Complete ===")
    print(f"Executable created at: {os.path.join(dist_dir, 'WarehouseGUI.exe')}")
    print("\n=== Portable Setup Instructions ===")
    print("1. Copy 'dist/WarehouseGUI.exe' to your USB drive.")
    print("2. Copy the 'images' folder (if it exists) to the same directory as the EXE on the USB drive.")
    print("3. Copy 'warehouse.db' (if you want to keep data) to the same directory as the EXE.")
    print("   If no DB is copied, a new empty one will be created on first run.")

if __name__ == "__main__":
    if sys.platform != "win32":
        print("WARNING: This script is intended to be run on Windows to generate a Windows executable.")
        print("Running it on macOS/Linux might generate a binary for that OS instead.")
        confirm = input("Do you want to continue? (y/n): ")
        if confirm.lower() != 'y':
            sys.exit()
            
    create_windows_executable()
