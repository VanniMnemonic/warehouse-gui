import sys
import asyncio
from PyQt6.QtWidgets import QApplication
from qasync import QEventLoop
from warehouse.database import init_db, engine
from warehouse.ui.main_window import MainWindow

async def run_app():
    # print("Inizializzazione DB...")
    await init_db()
    # print("DB Inizializzato.")
    
    stop_event = asyncio.Event()
    # print("Creazione MainWindow...")
    window = MainWindow(stop_event)
    # print("MainWindow creata. Mostra finestra...")
    window.show()
    # print("Finestra mostrata. In attesa di chiusura...")
    
    try:
        # Wait until the window is closed
        await stop_event.wait()
    finally:
        # Cleanup
        await shutdown()

async def shutdown():
    print("Cleaning up resources...")
    await engine.dispose()
    print("Shutdown complete.")
    QApplication.instance().quit() # Force Qt to quit

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # Prevent implicit quit, let run_app handle it
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    try:
        with loop:
            loop.run_until_complete(run_app())
    except KeyboardInterrupt:
        pass
    except RuntimeError as e:
        if str(e) != "Event loop stopped before Future completed.":
            raise
    finally:
        # Assicuriamoci che tutto sia chiuso
        if loop.is_running():
            loop.stop()
        if not loop.is_closed():
            loop.close()
        sys.exit(0)

if __name__ == "__main__":
    main()
