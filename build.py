from os import system,unlink
from os.path import join,exists
from shutil import rmtree
from time import time,sleep
import sys,subprocess,json

from pick import pick

from jczx.jczxMainInfo import VERSION

# 检测虚拟环境中的库是否存在
pkgs, python_exec =[], join("sde", 'Scripts', 'python.exe')
if exists(python_exec):
    try:
        result = subprocess.check_output(
            [python_exec, '-m', 'pip', 'list', '--format', 'json'],
            stderr = subprocess.PIPE,
            universal_newlines = True
        )
        packages = json.loads(result)
        pkgs = [pkg['name'].lower() for pkg in packages]
    except subprocess.CalledProcessError as e:
        print(f"执行pip命令时出错: {e.stderr}")
else:
    print(f"虚拟环境中未找到Python解释器: {python_exec}")
if not all([True if name in pkgs else False for name in ['pick', 'pyinstaller', 'nuitka', 'opencv-python', 'numpy', 'pyqt6', 'requests', 'paddlepaddle', 'paddleocr']]) or not pkgs:
    (print("正在准备环境"), sleep(3), system(".\\SDE.bat"))
else:
    (print("环境就绪"), sleep(3))

# 构建程序
version = VERSION if VERSION[-1].isdigit() else VERSION[:-1]
(_, index), startTime = pick(["pyinstaller", "nuitka"], "Please select a packaging method:", "->", 0, clear_screen = False), time()
match index:
    case 0:
        try:
            unlink(join("dist", "JCZXAutoScript.exe"))
            rmtree("build")
        except: ...
        finally:
            system('.\\sde\\Scripts\\activate && pyinstaller -Fw jczx/jczx.py \
                --name JCZXAutoScript \
                --additional-hooks-dir "hooks" \
                --add-data "jczx/resources;resources" \
                --add-data "jczx/OCR;OCR" \
                --add-data "sde/Lib/site-packages/paddleocr/tools;paddleocr/tools" \
                --clean \
                --noconfirm')
    case 1:
        try:
            unlink(join("dist","JCZXAutoScript-NuitkaCreate.exe"))
        except: ...
        finally:
            system(f".\\sde\\Scripts\\activate && python -m nuitka --show-progress \
                --show-memory \
                --standalone \
                --onefile \
                --output-dir=dist \
                --output-filename=JCZXAutoScript-NuitkaCreate.exe \
                --product-name=JCZXAutoScript \
                --product-version={version} \
                --enable-plugin=pyqt6 \
                --windows-console-mode=disable \
                --follow-imports \
                --include-data-dir=jczx/resources=resources \
                --include-data-dir=jczx/OCR=OCR \
                --remove-output jczx/jczx.py")
print("running time {}m {}s".format(*divmod(int(time() - startTime), 60)))