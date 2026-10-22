"""Draw the Plotweaver icon: an index card with three story threads weaving across it.
Writes plotweaver/resources/icon.png (256px) and packaging/windows/plotweaver.ico (multi-size).
Run from the repo root:  python tools/make_icon.py   (needs Pillow for the .ico)"""
import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QLinearGradient, QPainter, QPainterPath, QPen

ROOT = Path(__file__).resolve().parent.parent


def draw(size: int) -> QImage:
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    s = size / 256.0
    p.scale(s, s)
    bg = QPainterPath()
    bg.addRoundedRect(QRectF(8, 8, 240, 240), 52, 52)
    g = QLinearGradient(0, 0, 256, 256)
    g.setColorAt(0, QColor("#3a2a6e"))
    g.setColorAt(1, QColor("#7b4fc6"))
    p.fillPath(bg, g)
    # the card
    p.save()
    p.translate(128, 132)
    p.rotate(-7)
    card = QPainterPath()
    card.addRoundedRect(QRectF(-84, -62, 168, 124), 12, 12)
    p.fillPath(card.translated(0, 6), QColor(0, 0, 0, 60))
    p.fillPath(card, QColor("#fbf6ea"))
    p.setPen(QPen(QColor("#e4b5a8"), 3))
    p.drawLine(QPointF(-70, -36), QPointF(70, -36))  # the red rule on an index card
    p.restore()
    # three threads weaving across
    # three threads crossing over and under each other: (color, start y, control ys, end y)
    threads = [
        ("#4e9ad6", 176, (176, 96), 92),
        ("#f2b134", 132, (88, 178), 134),
        ("#e15759", 88, (92, 176), 176),
    ]
    for color, y0, (c1, c2), y1 in threads:
        path = QPainterPath()
        path.moveTo(28, y0)
        path.cubicTo(96, c1, 160, c2, 228, y1)
        p.setPen(QPen(QColor(0, 0, 0, 55), 16, Qt.SolidLine, Qt.RoundCap))
        p.drawPath(path.translated(0, 3))
        p.setPen(QPen(QColor(color), 12, Qt.SolidLine, Qt.RoundCap))
        p.drawPath(path)
    p.end()
    return img


def main():
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    png = ROOT / "plotweaver" / "resources" / "icon.png"
    png.parent.mkdir(parents=True, exist_ok=True)
    draw(256).save(str(png))
    sizes = [16, 24, 32, 48, 64, 128, 256]
    tmp = []
    for n in sizes:
        f = ROOT / "packaging" / f"_icon_{n}.png"
        draw(n).save(str(f))
        tmp.append(f)
    try:
        from PIL import Image
        imgs = [Image.open(f) for f in tmp]
        ico = ROOT / "packaging" / "windows" / "plotweaver.ico"
        imgs[-1].save(ico, sizes=[(n, n) for n in sizes], append_images=imgs[:-1])
        print("wrote", ico)
    except ImportError:
        print("Pillow not installed: skipped the .ico")
    for f in tmp:
        f.unlink()
    print("wrote", png)


if __name__ == "__main__":
    main()
