from os import system

name = input("name：")
try:
    system(f'F:/leidian/LDPlayer9/adb.exe -s emulator-5554 exec-out screencap -p > {name}.png')
except:
    ...
