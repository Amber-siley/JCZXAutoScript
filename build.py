from os import system,unlink
from os.path import join
from shutil import rmtree
from time import time

from pick import pick

from jczx.jczxMainInfo import VERSION

version = VERSION if VERSION[-1].isdigit() else VERSION[:-1]
(_, index), startTime = pick(["pyinstaller", "nuitka"], "Please select a packaging metho:", "->", 0, clear_screen = False), time()
match index:
    case 0:
        try:
            unlink(join("dist", "JCZXAutoScript.exe"))
            rmtree("build")
        finally:
            system('pyinstaller -Fw jczx/jczx.py --name JCZXAutoScript --add-data "jczx/resources;resources"')
    case 1:
        try:
            unlink(join("dist","JCZXAutoScript-NuitkaCreate.exe"))
        finally:    
            system(f"python -m nuitka --show-progress --show-memory --standalone --onefile --output-dir=dist --output-filename=JCZXAutoScript-NuitkaCreate.exe --product-name=JCZXAutoScript --product-version={version} --enable-plugin=pyqt6 --windows-console-mode=disable --include-data-dir=jczx/resources=resources --remove-output jczx/jczx.py")
print("running time {}m {}s".format(*divmod(int(time() - startTime), 60)))