import uvicorn
import webbrowser
import threading
import os
import sys


def open_browser():
    webbrowser.open("http://localhost:8000")


def main():
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    threading.Timer(1.0, open_browser).start()
    uvicorn.run(
        "taskView.server:app",
        host="127.0.0.1",
        port=8000,
        log_level="info",
    )


if __name__ == "__main__":
    main()
