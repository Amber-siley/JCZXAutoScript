import subprocess
from .base import EmulatorStrategy


class MuMuStrategy(EmulatorStrategy):
    def __init__(self, path: str, startupinfo):
        self._path = path
        self._startupinfo = startupinfo

    def _run(self, *args):
        cmd = [self._path] + list(args)
        subprocess.run(cmd, startupinfo=self._startupinfo, check=True)

    def launch(self, index: str):
        self._run("control", "-v", index, "launch")
        return True

    def shutdown(self, index: str):
        self._run("control", "-v", index, "shutdown")
        return True
