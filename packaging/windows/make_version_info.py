"""Write version_info.txt (the version shown in Windows' file Properties) from plotweaver/__init__.py."""
import re
from pathlib import Path

root = Path(__file__).resolve().parents[2]
version = re.search(r'__version__\s*=\s*"([^"]+)"', (root / "plotweaver" / "__init__.py").read_text()).group(1)
nums = [int(x) for x in re.findall(r"\d+", version)[:3]] + [0] * 4
v4 = tuple(nums[:4])
(root / "packaging" / "windows" / "version_info.txt").write_text(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={v4}, prodvers={v4}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'sierrax'),
      StringStruct('FileDescription', 'Plotweaver novel outliner'),
      StringStruct('FileVersion', '{version}'),
      StringStruct('InternalName', 'Plotweaver'),
      StringStruct('OriginalFilename', 'Plotweaver.exe'),
      StringStruct('ProductName', 'Plotweaver'),
      StringStruct('ProductVersion', '{version}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""", encoding="utf-8")
print(version)
