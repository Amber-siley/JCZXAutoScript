from os import system,unlink
from os.path import join
from shutil import rmtree

try:
    exe = join("dist", "JCZXAutoScript.exe")
    unlink(exe)
    rmtree("build")
except:
    ...
system('pyinstaller -Fw jczx.py --name JCZXAutoScript --add-data "resources;resources"')