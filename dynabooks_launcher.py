"""DynaBooks standalone launcher.

Starts Flask server, opens browser, and shows a system tray icon.
Uses a fixed port and lock file to enforce single-instance.
"""

import json
import os
import socket
import sys
import threading
import webbrowser


def _load_build_config() -> dict:
    """Load build_config.json from the bundled package or project root."""
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    cfg_path = os.path.join(base, 'build_config.json')
    if os.path.isfile(cfg_path):
        with open(cfg_path) as f:
            return json.load(f)
    return {"tier": "Light", "app_name": "DynaBooks Light", "dist_folder": "DynaBooks-Light"}


BUILD_CONFIG = _load_build_config()
APP_NAME = BUILD_CONFIG["app_name"]

# Fixed port so we can detect a running instance
DYNABOOKS_PORT = 52525
LOCK_FILE = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
    "DynaBooks",
    "dynabooks.lock",
)


def _is_already_running():
    """Check if another instance is already serving on our fixed port."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            s.connect(("127.0.0.1", DYNABOOKS_PORT))
            return True
    except (ConnectionRefusedError, OSError):
        return False


def _write_lock():
    """Write a lock file with our PID."""
    os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))


def _remove_lock():
    """Remove the lock file."""
    try:
        os.remove(LOCK_FILE)
    except OSError:
        pass


def _register_default_company():
    """Register the default seeded company in the multi-company registry
    if it isn't there already, so it shows up in the company selector."""
    from backend.company_manager import list_companies, _load_registry, _save_registry
    from backend.data_dir import get_db_path

    import os
    if not os.path.isfile(get_db_path()):
        return

    companies = list_companies()
    # Check if any company already points to the default DB
    if companies:
        return

    # Read entity name from the default DB
    from backend.config import make_session
    session = make_session()
    if not session.entity:
        session.close()
        return
    name = session.entity.name
    year_start = session.entity.year_start
    locale = session.entity.locale or "en_CA"
    session.close()

    # Register it
    from datetime import datetime
    import re
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower().strip()).strip('-')
    registry = _load_registry()
    registry.append({
        "slug": slug,
        "name": name,
        "year_start": year_start,
        "locale": locale,
        "created": datetime.now().isoformat(),
        "default": True,
    })
    _save_registry(registry)


HEARTBEAT_TIMEOUT = 15  # seconds without a heartbeat before auto-shutdown


def _start_heartbeat_watchdog():
    """Background thread: exit the process if the browser stops sending heartbeats."""
    import time
    from backend.app import heartbeat_state

    while True:
        time.sleep(5)
        if heartbeat_state["active"]:
            elapsed = time.time() - heartbeat_state["last"]
            if elapsed > HEARTBEAT_TIMEOUT:
                _remove_lock()
                os._exit(0)


def main():
    url = f"http://127.0.0.1:{DYNABOOKS_PORT}"

    # Single-instance check: if already running, just open browser and exit
    if _is_already_running():
        webbrowser.open(url)
        return

    # Initialize database and seed if needed
    from backend.config import init_db, make_session
    from backend.services.seeder import seed

    init_db()
    try:
        seed()
    except Exception:
        pass  # Already seeded or using multi-company mode

    # Ensure the default company is registered in the multi-company list
    _register_default_company()

    # Write lock file
    _write_lock()

    # Create Flask app
    from backend.app import create_app

    app = create_app()

    # Open browser after a short delay
    def open_browser():
        import time
        time.sleep(1.5)
        webbrowser.open(url)

    threading.Thread(target=open_browser, daemon=True).start()

    # Monitor browser heartbeat — auto-shutdown when all tabs close
    threading.Thread(target=_start_heartbeat_watchdog, daemon=True).start()

    # Try to set up system tray icon
    try:
        _run_with_tray(app, url)
    except ImportError:
        # pystray not available, just run Flask directly
        print(f"{APP_NAME} running at {url}")
        try:
            app.run(host="127.0.0.1", port=DYNABOOKS_PORT, debug=False, use_reloader=False)
        finally:
            _remove_lock()


def _run_with_tray(app, url):
    """Run Flask server with a system tray icon."""
    import pystray
    from PIL import Image, ImageDraw

    # Create a simple icon (blue square with "D")
    def create_icon_image():
        img = Image.new("RGB", (64, 64), "#1B3A5C")
        draw = ImageDraw.Draw(img)
        draw.text((22, 16), "D", fill="white")
        return img

    def on_open(icon, item):
        webbrowser.open(url)

    def on_quit(icon, item):
        icon.stop()
        _remove_lock()
        os._exit(0)

    menu = pystray.Menu(
        pystray.MenuItem("Open in Browser", on_open, default=True),
        pystray.MenuItem("Quit", on_quit),
    )

    icon = pystray.Icon(APP_NAME, create_icon_image(), APP_NAME, menu)

    # Run Flask in a background thread
    server_thread = threading.Thread(
        target=lambda: app.run(
            host="127.0.0.1", port=DYNABOOKS_PORT, debug=False, use_reloader=False
        ),
        daemon=True,
    )
    server_thread.start()

    # Run tray icon on main thread (required on Windows)
    print(f"{APP_NAME} running at {url}")
    icon.run()


if __name__ == "__main__":
    main()
