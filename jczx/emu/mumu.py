import json
import subprocess
import time
from .base import EmulatorStrategy


class MuMuStrategy(EmulatorStrategy):
    def __init__(self, path: str, startupinfo):
        self._path = path
        self._startupinfo = startupinfo

    def _run(self, *args):
        cmd = [self._path] + list(args)
        subprocess.run(cmd, startupinfo=self._startupinfo, check=True)

    def _info(self, index: str) -> dict:
        try:
            result = subprocess.run(
                [self._path, "info", "-v", index],
                capture_output=True,
                startupinfo=self._startupinfo,
                check=True,
            )
            return json.loads(result.stdout.decode("utf-8"))
        except Exception:
            return {}

    def launch(self, index: str):
        self._run("control", "-v", index, "launch")
        return True

    def shutdown(self, index: str):
        self._run("control", "-v", index, "shutdown")
        return True

    def wait_started(self, index: str, timeout: int = 120) -> bool:
        elapsed = 0
        interval = 2
        while elapsed < timeout:
            info = self._info(index)
            if info.get("is_android_started") and info.get("player_state") == "start_finished":
                return True
            time.sleep(interval)
            elapsed += interval
        return False
