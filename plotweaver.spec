# PyInstaller build recipe:  pyinstaller --noconfirm plotweaver.spec
# Produces dist/Plotweaver/ (a folder with Plotweaver.exe or Plotweaver plus its libraries).
# The portable zip, the Windows installer and the Linux AppImage are all made from that folder.
import sys

block_cipher = None
is_win = sys.platform.startswith("win")

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[("plotweaver/resources", "plotweaver/resources")],
    hiddenimports=[],
    excludes=["tkinter", "unittest", "pydoc", "PySide6.QtNetwork", "PySide6.QtQml", "PySide6.QtQuick",
              "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtMultimedia",
              "PySide6.Qt3DCore", "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtPdf"],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Plotweaver",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon="packaging/windows/plotweaver.ico" if is_win else None,
    version="packaging/windows/version_info.txt" if is_win else None,
)
coll = COLLECT(exe, a.binaries, a.zipped_data, a.datas, strip=False, upx=False, name="Plotweaver")
