from PyInstaller.utils.hooks import collect_submodules,collect_data_files

datas = collect_data_files("paddle", include_py_files = True)
hiddenimports = collect_submodules('paddle')