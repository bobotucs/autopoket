"""Start the AutoPocket v2 web app: python run_v2.py [--port 8766] [--no-browser]

Runs beside v1 (run.py, port 8765) so both can be open at once. The port defaults to
$PORT when set, else 8766.
"""
import argparse
import os
import threading
import webbrowser

import uvicorn

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8766)))
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    url = f"http://127.0.0.1:{a.port}"
    if not a.no_browser:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    print(f"AutoPocket v2 running at {url}  (Ctrl+C to stop)")
    uvicorn.run("autopocket2.server:app", host="127.0.0.1", port=a.port, log_level="warning")
