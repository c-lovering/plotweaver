#!/usr/bin/env bash
# Build dist/Plotweaver-<version>-x86_64.AppImage from the PyInstaller folder.
# Run from the repo root after:  pyinstaller --noconfirm plotweaver.spec
set -euo pipefail
cd "$(dirname "$0")/../.."
VERSION=$(python3 -c 'import re;print(re.search(r"__version__\s*=\s*\"([^\"]+)\"",open("plotweaver/__init__.py").read()).group(1))')
APPDIR=build/Plotweaver.AppDir
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp -a dist/Plotweaver/. "$APPDIR/usr/bin/"
cp packaging/linux/plotweaver.desktop "$APPDIR/plotweaver.desktop"
cp packaging/linux/plotweaver.desktop "$APPDIR/usr/share/applications/"
cp packaging/linux/plotweaver.png "$APPDIR/plotweaver.png"
cp packaging/linux/plotweaver.png "$APPDIR/usr/share/icons/hicolor/256x256/apps/"
cat > "$APPDIR/AppRun" <<'RUN'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/Plotweaver" "$@"
RUN
chmod +x "$APPDIR/AppRun"
TOOL=build/appimagetool-x86_64.AppImage
if [ ! -x "$TOOL" ]; then
  curl -fsSL -o "$TOOL" https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
  chmod +x "$TOOL"
fi
mkdir -p dist
ARCH=x86_64 "$TOOL" --appimage-extract-and-run "$APPDIR" "dist/Plotweaver-$VERSION-x86_64.AppImage"
echo "dist/Plotweaver-$VERSION-x86_64.AppImage"
