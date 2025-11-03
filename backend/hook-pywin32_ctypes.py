from PyInstaller.utils.hooks import collect_submodules, copy_metadata

hiddenimports = collect_submodules('pywin32_ctypes')
datas = copy_metadata('pywin32_ctypes')