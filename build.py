from os import system,unlink
from os.path import join
from shutil import rmtree

exe = join("dist", "JCZXAutoScript.exe")
unlink(exe)
rmtree("build")
system('pyinstaller -Fw jczx.py --name JCZXAutoScript --add-data "resources;resources"')