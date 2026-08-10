from os import unlink
from os.path import join, exists
from shutil import rmtree
from time import time
import subprocess

from pick import pick

from jczx.jczxMainInfo import VERSION


def _run(cmd: str) -> None:
    subprocess.run(cmd, shell=True, check=False)


_run("uv sync")

version = VERSION if VERSION[-1].isdigit() else VERSION[:-1]
(_, index), startTime = pick(
    ["pyinstaller", "nuitka"],
    "Please select a packaging method:",
    "->",
    0,
    clear_screen=False,
), time()

match index:
    case 0:
        for d in [join("dist", "JCZXAutoScript"), "build"]:
            try:
                rmtree(d)
            except OSError:
                pass
        _run(
            'uv run pyinstaller --onedir main.py '
            '--name JCZXAutoScript '
            '--additional-hooks-dir "hooks" '
            '--add-data "jczx/Config;jczx/Config" '
            '--add-data "jczx/resources;jczx/resources" '
            '--add-data "jczx/OCR;jczx/OCR" '
            '--add-data "jczx/Css;jczx/Css" '
            '--collect-all paddleocr '
            '--collect-all paddlex '
            '--collect-all textual '
            '--collect-all rich '
            '--copy-metadata opencv-contrib-python '
            '--copy-metadata python-bidi '
            '--copy-metadata imagesize '
            '--copy-metadata shapely '
            '--copy-metadata pyclipper '
            '--copy-metadata pypdfium2 '
            '--clean '
            '--noconfirm --console'
        )
    case 1:
        for d in [
            join("dist", "JCZXAutoScript-NuitkaCreate.dist"),
            join("dist", "JCZXAutoScript-NuitkaCreate.build"),
        ]:
            try:
                rmtree(d)
            except OSError:
                pass
        _run(
            f'uv run python -m nuitka --show-progress '
            '--show-memory '
            '--standalone '
            '--output-dir=dist '
            '--output-filename=JCZXAutoScript-NuitkaCreate.exe '
            '--product-name=JCZXAutoScript '
            f'--product-version={version} '
            '--follow-imports '
            '--include-data-dir=jczx/Config=jczx/Config '
            '--include-data-dir=jczx/resources=jczx/resources '
            '--include-data-dir=jczx/OCR=jczx/OCR '
            '--include-data-dir=jczx/Css=jczx/Css '
            '--remove-output main.py'
        )

rt = time() - startTime
print(f"running time {int(rt // 60)}m {int(rt % 60)}s")
