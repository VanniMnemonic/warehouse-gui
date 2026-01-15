import sys
import asyncio
from PyQt6.QtWidgets import QApplication
from qasync import QEventLoop
from warehouse.database import init_db
from warehouse.ui.main_window import MainWindow

async def start_app():
    await init_db()
    
    window = MainWindow()
    window.show()
    
    # Keep reference to window so it doesn't get GC'd
    return window

def main():
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    with loop:
        # We need to keep the window alive
        window = loop.run_until_complete(start_app())
        loop.run_forever()

if __name__ == "__main__":
    main()
