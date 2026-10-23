"""Run against a verification build; no production profile, updater network or scripts."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


def smoke(executable):
    with tempfile.TemporaryDirectory(prefix="myway-frozen-smoke-") as tmp:
        root = Path(tmp)
        profile, raw = root / "MyWayTools", root / "raw"
        profile.mkdir()
        raw.mkdir()
        (profile / "config.json").write_text(json.dumps({"sharepoint_root": str(root), "raw_files_path": str(raw)}))
        (profile / ".env").write_text("")
        env = os.environ.copy()
        env.update(APPDATA=str(root), QT_QPA_PLATFORM="offscreen", HTTPS_PROXY="http://127.0.0.1:9",
                   HTTP_PROXY="http://127.0.0.1:9", ALL_PROXY="http://127.0.0.1:9", NO_PROXY="")
        process = subprocess.Popen([str(Path(executable).resolve())], env=env,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            end = time.monotonic() + 30
            while time.monotonic() < end and process.poll() is None:
                if (profile / "workflows.json").exists() and (profile / "history.db").exists():
                    break
                time.sleep(.1)
            assert (profile / "preferences.json").exists(), "Frozen app did not initialize preferences"
            assert (profile / "history.db").exists(), "Frozen app did not initialize history"
            assert (profile / "workflows.json").exists(), "Frozen app did not initialize workflows"
            time.sleep(2)
            assert process.poll() is None, f"Frozen app exited unexpectedly: {process.returncode}"
            favorites = json.loads((profile / "preferences.json").read_text())["favorites"]
            assert len(favorites) == 5
            print("FROZEN_STARTUP_OK: isolated profile, five favorites, SQLite and workflows initialized")
        finally:
            if process.poll() is None:
                process.terminate()  # Only the test-owned idle GUI, never an operational process.
            process.wait(timeout=10)


if __name__ == "__main__":
    smoke(sys.argv[1])
