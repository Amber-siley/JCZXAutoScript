from os import unlink
from os.path import join, exists
from shutil import rmtree
from time import time, sleep
import subprocess, json

from pick import pick

from jczx.jczxMainInfo import VERSION


def _run(cmd: str) -> None:
    subprocess.run(cmd, shell=True, check=False)


# 检测虚拟环境中的库是否存在
pkgs, python_exec = [], join(".venv", "Scripts", "python.exe")
if exists(python_exec):
    try:
        result = subprocess.check_output(
            [python_exec, "-m", "pip", "list", "--format", "json"],
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        packages = json.loads(result)
        pkgs = [pkg["name"].lower() for pkg in packages]
    except subprocess.CalledProcessError as e:
        print(f"执行pip命令时出错: {e.stderr}")
else:
    print(f"虚拟环境中未找到Python解释器: {python_exec}")

build_deps = [
    "pick",
    "pyinstaller",
    "nuitka",
    "opencv-python",
    "onnxruntime",
    "paddleocr",
    "rich",
    "textual",
    "uiautomator2",
    "requests",
    "fastapi",
    "uvicorn",
]
if not all(name in pkgs for name in build_deps) or not pkgs:
    print("正在准备环境")
    sleep(3)
    _run("uv sync")
else:
    print("环境就绪")
    sleep(3)

# 构建程序
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
        try:
            unlink(join("dist", "JCZXAutoScript.exe"))
            rmtree("build")
        except:
            ...
        finally:
            _run(
                '.venv\\Scripts\\activate && pyinstaller -F jczx/jczxCli.py '
                '--name JCZXAutoScript '
                '--additional-hooks-dir "hooks" '
                '--add-data "jczx/resources;resources" '
                '--add-data "jczx/OCR;OCR" '
                '--clean '
                '--noconfirm --console'
            )
    case 1:
        try:
            unlink(join("dist", "JCZXAutoScript-NuitkaCreate.exe"))
        except:
            ...
        finally:
            _run(
                f'.venv\\Scripts\\activate && python -m nuitka --show-progress '
                '--show-memory '
                '--standalone '
                '--onefile '
                '--output-dir=dist '
                '--output-filename=JCZXAutoScript-NuitkaCreate.exe '
                '--product-name=JCZXAutoScript '
                '--product-version={version} '
                '--follow-imports '
                '--include-data-dir=jczx/resources=resources '
                '--include-data-dir=jczx/OCR=OCR '
                '--remove-output jczx/jczxCli.py'
            )

rt = time() - startTime
print(f"running time {int(rt // 60)}m {int(rt % 60)}s")
