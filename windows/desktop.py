"""Windows desktop controller and headless packaging smoke test.

The business application runs locally; closing this controller stops its server.
No external Python packages are needed outside the executable build process.
"""

import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import urllib.request
import webbrowser
from http.server import ThreadingHTTPServer


SOURCE_ROOT = Path(__file__).resolve().parents[1]
RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", SOURCE_ROOT))
if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(SOURCE_ROOT))
import app  # noqa: E402

app.ROOT = RESOURCE_ROOT


def data_path():
    """Keep business data outside the executable and its extraction directory."""
    if os.environ.get("SALES_DB"):
        return Path(os.environ["SALES_DB"]).expanduser().resolve()
    local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return local / "NexvantEngineering" / "data" / "sales.db"


def copy_database(source_path, destination):
    """Copy a live SQLite database without replacing an existing desktop file."""
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError(f"A desktop database already exists at {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix="import-", suffix=".db", dir=destination.parent, delete=False) as handle:
            temporary = Path(handle.name)
        with closing(sqlite3.connect(f"{Path(source_path).resolve().as_uri()}?mode=ro", uri=True)) as source, closing(sqlite3.connect(temporary)) as target:
            with target:
                source.backup(target)
                if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise RuntimeError("Database integrity check failed")
        # Connections are closed before moving the file for Windows locking.
        # Windows rename refuses an existing destination; hard-link creation
        # gives the same no-overwrite guarantee on the Linux validation host.
        if os.name == "nt":
            temporary.rename(destination)
        else:
            os.link(temporary, destination)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


class LocalServer:
    def __init__(self, database, host="127.0.0.1", port=8000):
        app.DB_PATH = Path(database)
        app.initialize()
        self.httpd = ThreadingHTTPServer((host, port), app.Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def url(self):
        return f"http://127.0.0.1:{self.httpd.server_port}"

    def start(self):
        self.thread.start()
        # A real request catches initialization, routing and database failures.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(self.url + "/api/status", timeout=5) as response:
            result = json.load(response)
            if response.status != 200 or not all(
                isinstance(result.get(key), bool) for key in ("setup", "authenticated")
            ):
                raise RuntimeError("The application readiness check failed.")
        return result

    def stop(self):
        if self.thread.is_alive():
            self.httpd.shutdown()
            self.thread.join(timeout=5)
        self.httpd.server_close()
        app.SESSIONS.clear()


def smoke_test():
    """Use disposable data, never business data, to verify the packaged app."""
    with tempfile.TemporaryDirectory(prefix="nexvant-smoke-") as directory:
        server = LocalServer(Path(directory) / "sales.db", port=0)
        try:
            status = server.start()
            if status != {"setup": True, "authenticated": False}:
                raise RuntimeError("Unexpected first-run status")
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            for route, expected in (("/", b"<html"), ("/app.js", b"fetch"), ("/style.css", b"{")):
                with opener.open(server.url + route, timeout=5) as response:
                    if response.status != 200 or expected not in response.read():
                        raise RuntimeError(f"Missing or invalid bundled asset: {route}")
        finally:
            server.stop()


def main():
    import tkinter as tk
    from tkinter import messagebox, ttk

    root = tk.Tk()
    root.title("Nexvant Engineering — Sales & Finance")
    root.minsize(540, 390)
    root.geometry("620x450")
    root.configure(background="#f4f7fa")
    frame = ttk.Frame(root, padding=24)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="NEXVANT ENGINEERING", font=("Segoe UI", 19, "bold")).pack(anchor="w")
    ttk.Label(frame, text="Sales & Finance", font=("Segoe UI", 13)).pack(anchor="w", pady=(2, 20))
    status_text = tk.StringVar(value="Stopped")
    ttk.Label(frame, textvariable=status_text, font=("Segoe UI", 11)).pack(anchor="w", pady=(0, 14))
    lan = tk.BooleanVar(value=False)
    lan_check = ttk.Checkbutton(frame, text="Allow phones on my trusted private network", variable=lan)
    lan_check.pack(anchor="w")
    ttk.Label(frame, text="Enable only on trusted Wi-Fi. On Android, use this PC's LAN IPv4\naddress on port 8000. Windows Firewall must allow private networks only.", wraplength=550).pack(anchor="w", pady=(4, 16))
    database = data_path()
    ttk.Label(frame, text=f"Business data: {database}", wraplength=550).pack(anchor="w", pady=(0, 16))
    buttons = ttk.Frame(frame)
    buttons.pack(anchor="w")
    server = None

    def start():
        nonlocal server
        if server is not None:
            return
        try:
            server = LocalServer(database, "0.0.0.0" if lan.get() else "127.0.0.1")
            server.start()
        except Exception as error:
            if server is not None:
                server.stop()
                server = None
            messagebox.showerror("Could not start Nexvant", f"{error}\n\nIf port 8000 is in use, stop the other application or Nexvant instance first.")
            return
        status_text.set("Running on port 8000" + (" · private-network access enabled" if lan.get() else " · this PC only"))
        start_button.configure(state="disabled")
        open_button.configure(state="normal")
        stop_button.configure(state="normal")
        lan_check.configure(state="disabled")
        webbrowser.open(server.url)

    def stop():
        nonlocal server
        if server is not None:
            server.stop()
            server = None
        status_text.set("Stopped — business data is retained")
        start_button.configure(state="normal")
        open_button.configure(state="disabled")
        stop_button.configure(state="disabled")
        lan_check.configure(state="normal")

    def close():
        stop()
        root.destroy()

    start_button = ttk.Button(buttons, text="Start", command=start)
    start_button.pack(side="left", padx=(0, 8))
    open_button = ttk.Button(buttons, text="Open application", state="disabled", command=lambda: webbrowser.open(server.url) if server else None)
    open_button.pack(side="left", padx=(0, 8))
    stop_button = ttk.Button(buttons, text="Stop", state="disabled", command=stop)
    stop_button.pack(side="left")
    ttk.Label(frame, text="Closing this window stops the server. Your database stays on this PC.\nThe first run asks you to create your own administrator and clearing passwords.", wraplength=550).pack(anchor="w", pady=(20, 0))
    root.protocol("WM_DELETE_WINDOW", close)

    # Existing repository users can copy their data safely using SQLite's backup API.
    legacy = SOURCE_ROOT / "data" / "sales.db"
    if not database.exists() and not getattr(sys, "frozen", False) and legacy.exists() and not os.environ.get("SALES_DB"):
        migrate = messagebox.askyesnocancel("Existing sales database", "An existing repository database was found. Copy it into this desktop application's data folder?\n\nYes: copy existing records.\nNo: start a new database.\nCancel: exit without changes.")
        if migrate is None:
            root.destroy()
            return
        if migrate:
            try:
                copy_database(legacy, database)
            except Exception as error:
                messagebox.showerror("Database import failed", str(error))
                root.destroy()
                return
    root.after(100, start)
    root.mainloop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke-test", action="store_true", help="Test bundled HTTP server and assets using disposable data, then exit")
    args = parser.parse_args()
    if args.smoke_test:
        smoke_test()
    else:
        main()
