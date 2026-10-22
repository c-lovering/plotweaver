"""Corkboard and screen-time matrix views."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QHBoxLayout,
                               QHeaderView, QLabel, QMenu, QScrollArea, QSlider, QSpinBox,
                               QStyledItemDelegate, QTableWidget, QTableWidgetItem, QToolButton,
                               QToolTip, QVBoxLayout, QWidget)

from ..model import CHAPTER_NUM_RE, Entity, Project, Query, as_list, natural_key, strip_link
from .theme import is_dark, muted
from .widgets import STATUS_COLORS

PALETTE = ["#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f", "#edc948", "#b07aa1",
           "#ff9da7", "#9c755f", "#86bcb6", "#d37295", "#a0cbe8"]
NONE_COLOR = "#c4c4c4"
PATH_ROLE = Qt.UserRole


def project_key(project: Project) -> str:
    return hashlib.md5(str(project.root).encode("utf-8")).hexdigest()[:12]


def color_map(values) -> dict:
    vals = sorted({v for v in values if v}, key=natural_key)
    return {v: PALETTE[i % len(PALETTE)] for i, v in enumerate(vals)}


def legend_html(cmap: dict, extra=None) -> str:
    chips = [f"<span style='color:{c}'>■</span>&nbsp;{v}" for v, c in cmap.items()]
    if extra:
        chips.append(extra)
    return "&nbsp;&nbsp;&nbsp;".join(chips)


def _toolbar_label(text):
    return QLabel(text)


def chapter_label(project: Project, ch: Entity) -> str:
    """Chapter name, prefixed with its position when the name doesn't already say it."""
    n = project.chapter_number(ch)
    if n is None:
        return ch.name
    m = CHAPTER_NUM_RE.match(ch.name)
    if m and int(m.group(3)) == n:
        return ch.name
    return f"{n} · {ch.name}"


# ============================================================================ corkboard

@dataclass
class Slot:
    kind: str           # "header", "card", "empty"
    rect: QRect
    text: str = ""
    entity: Entity | None = None   # scene (card) or chapter (empty)
    chapter: Entity | None = None


ZOOMS = [  # width, height
    (180, 64),
    (240, 168),
    (310, 220),
]


class CorkCanvas(QWidget):
    selected = Signal(object)          # path
    opened = Signal(object)            # path
    moveRequested = Signal(str, object, int)

    MARGIN, GAP = 18, 14

    def __init__(self, parent=None):
        super().__init__(parent)
        self.project: Project | None = None
        self.entries: list = []        # ("header", text) / ("card", scene, chapter) / ("empty", chapter)
        self.slots: list[Slot] = []
        self.zoom = 1
        self.color_of = lambda e: NONE_COLOR
        self.query = Query()
        self.drag_chapters = True
        self.current: Path | None = None
        self._press: tuple | None = None   # (pos, slot)
        self._dragging = False
        self._drop = None                  # (x, top, bottom, args)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self._layout_width = 0

    # ------------------------------------------------------------ layout
    def set_entries(self, entries):
        self.entries = entries
        self.relayout()

    def relayout(self):
        w = max(self.width(), 300)
        cw, ch = ZOOMS[self.zoom]
        m, g = self.MARGIN, self.GAP
        x, y = m, m
        row_h = 0
        self.slots = []
        hf = QFontMetrics(self._header_font())
        for ent in self.entries:
            if ent[0] == "header":
                if x > m:
                    y += row_h + g
                if self.slots:
                    y += 8
                h = hf.height() + 10
                self.slots.append(Slot("header", QRect(m, y, w - 2 * m, h), text=ent[1]))
                y += h + 4
                x, row_h = m, 0
                continue
            if x + cw > w - m and x > m:
                x = m
                y += row_h + g
                row_h = 0
            r = QRect(x, y, cw, ch)
            if ent[0] == "card":
                self.slots.append(Slot("card", r, entity=ent[1], chapter=ent[2]))
            else:
                self.slots.append(Slot("empty", r, entity=ent[1], chapter=ent[1]))
            row_h = max(row_h, ch)
            x += cw + g
        total = y + row_h + m
        self._layout_width = w
        self.setMinimumHeight(total)
        self.update()

    def resizeEvent(self, e):
        if e.size().width() != self._layout_width:
            self.relayout()
        super().resizeEvent(e)

    def rect_of(self, path) -> QRect | None:
        for s in self.slots:
            if s.entity is not None and (s.entity.path == path or
                                         (s.chapter is not None and s.chapter.path == path)):
                return s.rect
        return None

    # ------------------------------------------------------------ painting
    def _header_font(self):
        f = QFont(self.font())
        f.setPointSizeF(f.pointSizeF() * 1.25)
        f.setBold(True)
        return f

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pal = self.palette()
        p.fillRect(self.rect(), pal.window().color().darker(118 if is_dark() else 104))
        if not self.slots:
            p.setPen(muted(pal))
            p.drawText(self.rect(), Qt.AlignCenter,
                       "No chapters here yet.\nAdd chapters and scenes from the toolbar.")
        clip = ev.rect()
        for s in self.slots:
            if not s.rect.intersects(clip):
                continue
            if s.kind == "header":
                p.setPen(pal.windowText().color())
                p.setFont(self._header_font())
                p.drawText(s.rect.adjusted(2, 0, 0, -4), Qt.AlignLeft | Qt.AlignBottom, s.text)
                p.setPen(QPen(pal.mid().color(), 1))
                p.drawLine(s.rect.left(), s.rect.bottom(), s.rect.right(), s.rect.bottom())
            elif s.kind == "card":
                self._paint_card(p, s)
            else:
                self._paint_empty(p, s)
        if self._dragging and self._drop:
            x, top, bottom, _ = self._drop
            p.setOpacity(1)
            p.setPen(QPen(pal.highlight().color(), 4, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(x, top - 4, x, bottom + 4)
        p.end()

    def _dim(self, e: Entity) -> bool:
        return bool(self.query) and not self.query.matches(e)

    def _paint_frame(self, p, r: QRect, selected: bool, dashed=False):
        pal = self.palette()
        path = QPainterPath()
        path.addRoundedRect(QRectF(r).adjusted(0.5, 0.5, -0.5, -0.5), 6, 6)
        if not dashed:
            p.fillPath(path.translated(0, 2), QColor(0, 0, 0, 28))
            p.fillPath(path, pal.base())
        pen = QPen(pal.highlight().color(), 2.5) if selected else QPen(pal.mid().color(), 1)
        if dashed:
            pen.setStyle(Qt.DashLine)
        p.setPen(pen)
        p.drawPath(path)
        return path

    def _paint_card(self, p: QPainter, s: Slot):
        e, r = s.entity, s.rect
        pal = self.palette()
        p.save()
        p.setOpacity(0.28 if self._dim(e) else 1.0)
        sel = self.current is not None and (e.path == self.current or
                                            (s.chapter is not None and s.chapter.path == self.current))
        path = self._paint_frame(p, r, sel)
        # colored stripe
        p.save()
        p.setClipPath(path)
        p.fillRect(QRect(r.left(), r.top(), 7, r.height()), QColor(self.color_of(e)))
        p.restore()
        inner = r.adjusted(16, 8, -10, -8)
        small = QFont(self.font())
        small.setPointSizeF(small.pointSizeF() * 0.85)
        bold = QFont(self.font())
        bold.setBold(True)
        bold.setPointSizeF(bold.pointSizeF() * 1.05)
        sm, bm = QFontMetrics(small), QFontMetrics(bold)
        y = inner.top()
        # chapter label (omit when the scene is named the same as its chapter)
        if s.chapter is not None:
            p.setFont(small)
            p.setPen(muted(pal))
            label = chapter_label(self.project, s.chapter) if self.project else s.chapter.name
            p.drawText(QRect(inner.left(), y, inner.width(), sm.height()), Qt.AlignLeft,
                       sm.elidedText(label.upper(), Qt.ElideRight, inner.width()))
            y += sm.height() + 1
        p.setFont(bold)
        p.setPen(pal.text().color())
        p.drawText(QRect(inner.left(), y, inner.width(), bm.height()), Qt.AlignLeft,
                   bm.elidedText(e.name, Qt.ElideRight, inner.width()))
        y += bm.height() + 4
        if self.zoom == 0:
            p.restore()
            return
        # footer: POV, heat, words; tags above it
        footer_h = sm.height()
        tags_h = sm.height() + 2 if e.tags else 0
        footer_top = inner.bottom() - footer_h + 1
        body_rect = QRect(inner.left(), y, inner.width(), footer_top - tags_h - y - 4)
        summary = str(e.meta.get("summary") or "").strip()
        body_font = QFont(self.font())
        if summary:
            text = summary
            p.setPen(pal.text().color())
        else:
            text = self.project.snippet(e) if self.project else ""
            body_font.setItalic(True)
            p.setPen(muted(pal))
        p.setFont(body_font)
        if text and body_rect.height() > 8:
            self._draw_wrapped(p, body_rect, text, QFontMetrics(body_font))
        p.setFont(small)
        if e.tags:
            p.setPen(pal.highlight().color())
            tag_text = "  ".join("#" + t for t in e.tags)
            p.drawText(QRect(inner.left(), footer_top - tags_h, inner.width(), sm.height()), Qt.AlignLeft,
                       sm.elidedText(tag_text, Qt.ElideRight, inner.width()))
        p.setPen(muted(pal))
        pov = strip_link(e.meta.get("pov")) if e.meta.get("pov") else ""
        words = self.project.prose_words(e) if self.project else None
        right = f"{words:,} w" if words else ""
        rw = sm.horizontalAdvance(right) + (6 if right else 0)
        heat = 0
        try:
            heat = max(0, min(5, int(e.meta.get("heat") or 0)))
        except (TypeError, ValueError):
            pass
        heat_w = heat * 8 + (6 if heat else 0)
        left_w = inner.width() - rw - heat_w
        if pov:
            p.drawText(QRect(inner.left(), footer_top, left_w, footer_h), Qt.AlignLeft | Qt.AlignVCenter,
                       sm.elidedText("POV " + pov, Qt.ElideRight, left_w))
        if right:
            p.drawText(QRect(inner.right() - rw + 6, footer_top, rw, footer_h),
                       Qt.AlignRight | Qt.AlignVCenter, right)
        if heat:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#e15759"))
            hx = inner.right() - rw - heat_w + 6
            cy = footer_top + footer_h // 2
            for i in range(heat):
                p.drawEllipse(QPoint(hx + i * 8 + 3, cy), 3, 3)
        p.restore()

    @staticmethod
    def _draw_wrapped(p, rect: QRect, text: str, fm: QFontMetrics):
        """Word-wrap into rect, ending with an ellipsis if it doesn't fit."""
        lines, max_lines = [], max(1, rect.height() // fm.lineSpacing())
        for para in text.split("\n"):
            words = para.split()
            cur = ""
            for w in words:
                trial = (cur + " " + w).strip()
                if fm.horizontalAdvance(trial) <= rect.width() or not cur:
                    cur = trial
                else:
                    lines.append(cur)
                    cur = w
            lines.append(cur)
            if len(lines) > max_lines:
                break
        clipped = len(lines) > max_lines
        lines = lines[:max_lines]
        if clipped and lines:
            lines[-1] = fm.elidedText(lines[-1] + " …", Qt.ElideRight, rect.width())
        y = rect.top()
        for ln in lines:
            p.drawText(QRect(rect.left(), y, rect.width(), fm.height()), Qt.AlignLeft,
                       fm.elidedText(ln, Qt.ElideRight, rect.width()))
            y += fm.lineSpacing()

    def _paint_empty(self, p, s: Slot):
        pal = self.palette()
        p.save()
        p.setOpacity(0.28 if self._dim(s.entity) else 1.0)
        self._paint_frame(p, s.rect, s.entity.path == self.current, dashed=True)
        p.setPen(muted(pal))
        f = QFont(self.font())
        f.setBold(True)
        p.setFont(f)
        r = s.rect.adjusted(12, 8, -10, -8)
        fm = QFontMetrics(f)
        label = chapter_label(self.project, s.entity) if self.project else s.entity.name
        p.drawText(QRect(r.left(), r.top(), r.width(), fm.height()), Qt.AlignLeft,
                   fm.elidedText(label, Qt.ElideRight, r.width()))
        f.setBold(False)
        f.setItalic(True)
        p.setFont(f)
        p.drawText(r.adjusted(0, fm.height() + 4, 0, 0), Qt.AlignLeft | Qt.TextWordWrap,
                   "Chapter with no scenes yet")
        p.restore()

    # ------------------------------------------------------------ mouse
    def slot_at(self, pos) -> Slot | None:
        for s in self.slots:
            if s.kind != "header" and s.rect.contains(pos):
                return s
        return None

    def _nearest(self, pos) -> Slot | None:
        """Card under the pointer, or the closest one in the same row (for gaps)."""
        hit = self.slot_at(pos)
        if hit:
            return hit
        best, dist = None, None
        for s in self.slots:
            if s.kind == "header":
                continue
            r = s.rect
            if r.top() - self.GAP <= pos.y() <= r.bottom() + self.GAP:
                d = 0 if r.left() <= pos.x() <= r.right() else min(abs(pos.x() - r.left()),
                                                                    abs(pos.x() - r.right()))
                if d <= self.GAP * 3 and (dist is None or d < dist):
                    best, dist = s, d
        return best

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return super().mousePressEvent(e)
        s = self.slot_at(e.position().toPoint())
        self._press = (e.position().toPoint(), s) if s else None
        if s:
            self.current = s.entity.path
            self.update()
            self.selected.emit(s.entity.path)

    def mouseDoubleClickEvent(self, e):
        s = self.slot_at(e.position().toPoint())
        if s:
            self.opened.emit(s.entity.path)

    def _chapter_bounds(self, chapter) -> tuple[Slot, Slot] | None:
        mine = [s for s in self.slots if s.chapter is chapter and s.kind != "header"]
        return (mine[0], mine[-1]) if mine else None

    def _compute_drop(self, pos):
        src = self._press[1]
        t = self._nearest(pos)
        if t is None:
            return None
        after = pos.x() > t.rect.center().x()
        p = self.project
        if self.drag_chapters:
            mover, target = src.chapter, t.chapter
            if mover is None or target is None or mover is target:
                return None
            first, last = self._chapter_bounds(target)
            edge = last if after else first
            x = edge.rect.right() + self.GAP // 2 if after else edge.rect.left() - self.GAP // 2
            sibs = [c for c in p.siblings(target) if c is not mover]
            idx = sibs.index(target) + (1 if after else 0)
            parent = target.parent
            return (x, edge.rect.top(), edge.rect.bottom(),
                    (str(mover.path), str(parent.path) if parent else None, idx))
        if src.kind != "card":
            return None
        mover = src.entity
        if t.kind == "empty":
            r = t.rect
            return (r.left() + 3, r.top(), r.bottom(), (str(mover.path), str(t.entity.path), 0))
        if t.entity is mover:
            return None
        chap = t.chapter
        sibs = [c for c in chap.children if c is not mover]
        idx = sibs.index(t.entity) + (1 if after else 0)
        x = t.rect.right() + self.GAP // 2 if after else t.rect.left() - self.GAP // 2
        return (x, t.rect.top(), t.rect.bottom(), (str(mover.path), str(chap.path), idx))

    def mouseMoveEvent(self, e):
        pos = e.position().toPoint()
        if self._press and e.buttons() & Qt.LeftButton:
            if not self._dragging and (pos - self._press[0]).manhattanLength() > QApplication.startDragDistance():
                self._dragging = True
                self.setCursor(Qt.ClosedHandCursor)
            if self._dragging:
                self._drop = self._compute_drop(pos)
                sa = self._scroll_area()
                if sa:
                    sa.ensureVisible(pos.x(), pos.y(), 20, 40)
                self.update()

    def mouseReleaseEvent(self, e):
        if self._dragging:
            self.setCursor(Qt.ArrowCursor)
            drop = self._drop
            self._dragging, self._drop, self._press = False, None, None
            self.update()
            if drop:
                self.moveRequested.emit(*drop[3])
            return
        self._press = None

    def _scroll_area(self):
        w = self.parent()
        while w is not None and not isinstance(w, QScrollArea):
            w = w.parent()
        return w

    def event(self, ev):
        if ev.type() == ev.Type.ToolTip:
            s = self.slot_at(ev.pos())
            if s and s.kind == "card":
                e = s.entity
                bits = [f"<b>{e.name}</b>"]
                if s.chapter is not None:
                    bits.append(f"<i>{s.chapter.name}</i>")
                if e.meta.get("summary"):
                    bits.append(str(e.meta.get("summary")))
                chars = [strip_link(c) for c in as_list(e.meta.get("characters"))]
                if chars:
                    bits.append("With: " + ", ".join(chars))
                if e.tags:
                    bits.append(" ".join("#" + t for t in e.tags))
                QToolTip.showText(ev.globalPos(), "<br>".join(bits), self)
            else:
                QToolTip.hideText()
            return True
        return super().event(ev)


class CorkboardView(QWidget):
    selected = Signal(object)
    opened = Signal(object)
    moveRequested = Signal(str, object, int)

    COLOR_MODES = ["Status", "POV", "Thread", "Tag"]

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.project: Project | None = None
        self.query = Query()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 0)
        bar = QHBoxLayout()
        bar.setContentsMargins(8, 0, 8, 0)
        self.scope = QComboBox()
        self.scope.setMinimumContentsLength(14)
        self.scope.currentIndexChanged.connect(lambda *_: self._scope_changed())
        self.color = QComboBox()
        self.color.addItems(self.COLOR_MODES)
        self.color.setCurrentText(settings.value("cork/color", "Status", str))
        self.color.currentTextChanged.connect(self._color_changed)
        self.drag = QComboBox()
        self.drag.addItems(["Chapters", "Scenes"])
        self.drag.setToolTip("What dragging a card moves: its whole chapter, or just that scene.")
        self.drag.setCurrentText(settings.value("cork/drag", "Chapters", str))
        self.drag.currentTextChanged.connect(self._drag_changed)
        self.zoom = QSlider(Qt.Horizontal)
        self.zoom.setRange(0, len(ZOOMS) - 1)
        self.zoom.setPageStep(1)
        self.zoom.setFixedWidth(90)
        self.zoom.setValue(int(settings.value("cork/zoom", 1)))
        self.zoom.valueChanged.connect(self._zoom_changed)
        for w in (_toolbar_label("Show"), self.scope, _toolbar_label("  Color by"), self.color,
                  _toolbar_label("  Drag moves"), self.drag, _toolbar_label("  Size"), self.zoom):
            bar.addWidget(w)
        bar.addStretch(1)
        self.filter_label = QLabel()
        self.filter_label.setStyleSheet("color: palette(highlight);")
        bar.addWidget(self.filter_label)
        lay.addLayout(bar)
        self.legend = QLabel()
        self.legend.setTextFormat(Qt.RichText)
        self.legend.setContentsMargins(10, 0, 10, 0)
        self.legend.setWordWrap(True)
        lay.addWidget(self.legend)
        self.canvas = CorkCanvas()
        self.canvas.zoom = self.zoom.value()
        self.canvas.drag_chapters = self.drag.currentText() == "Chapters"
        self.canvas.selected.connect(self.selected)
        self.canvas.opened.connect(self.opened)
        self.canvas.moveRequested.connect(self.moveRequested)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.canvas)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        lay.addWidget(self.scroll, 1)

    # ------------------------------------------------------------ settings
    def _color_changed(self, t):
        self.settings.setValue("cork/color", t)
        self.refresh()

    def _drag_changed(self, t):
        self.settings.setValue("cork/drag", t)
        self.canvas.drag_chapters = t == "Chapters"

    def _zoom_changed(self, v):
        self.settings.setValue("cork/zoom", v)
        self.canvas.zoom = v
        self.canvas.relayout()

    def _scope_changed(self):
        if self.project and not self._filling:
            self.settings.setValue(f"cork/scope/{project_key(self.project)}", self.scope.currentData() or "")
            self.refresh()

    # ------------------------------------------------------------ data
    def set_project(self, project):
        self.project = project
        self.canvas.project = project
        self.canvas.current = None

    def set_current(self, path):
        self.canvas.current = Path(path) if path else None
        self.canvas.update()
        r = self.canvas.rect_of(self.canvas.current) if path else None
        if r is not None:
            self.scroll.ensureVisible(r.center().x(), r.center().y(), r.width() // 2 + 20, r.height() // 2 + 20)

    def set_query(self, q: Query):
        self.query = q
        self.canvas.query = q
        self.filter_label.setText("Filter: " + " ".join(["#" + t for t in q.tags] + q.words) if q else "")
        self.canvas.update()

    _filling = False

    def _fill_scope(self):
        p = self.project
        want = self.scope.currentData()
        if want is None:
            want = self.settings.value(f"cork/scope/{project_key(p)}", "", str)
        self._filling = True
        self.scope.clear()
        self.scope.addItem("Whole book", "")
        for part in (e for e in p.outline_roots() if e.type == "part"):
            self.scope.addItem(part.name, str(part.path))
        i = self.scope.findData(want)
        self.scope.setCurrentIndex(i if i >= 0 else 0)
        self._filling = False

    def refresh(self):
        p = self.project
        if not p:
            return
        self._fill_scope()
        scope_path = self.scope.currentData()
        scope = p.get(Path(scope_path)) if scope_path else None
        entries = []
        roots = [scope] if scope else p.outline_roots()
        has_parts = any(r.type == "part" for r in roots)
        loose_header = False

        def add_chapter(ch):
            scenes = [c for c in ch.children if c.type == "scene"]
            if scenes:
                entries.extend(("card", s, ch) for s in scenes)
            else:
                entries.append(("empty", ch))
        for r in roots:
            if r.type == "part":
                entries.append(("header", r.name))
                for ch in r.children:
                    if ch.type == "chapter":
                        add_chapter(ch)
                loose_header = False
            elif r.type == "chapter":
                if has_parts and not loose_header:
                    entries.append(("header", "Not in a part"))
                    loose_header = True
                add_chapter(r)
        scenes = [e[1] for e in entries if e[0] == "card"]
        mode = self.color.currentText()
        if mode == "Status":
            cmap = {s: STATUS_COLORS[s] for s in STATUS_COLORS}
            key = lambda e: e.status or "idea"
        elif mode == "POV":
            key = lambda e: strip_link(e.meta.get("pov")) if e.meta.get("pov") else ""
            cmap = color_map(key(s) for s in scenes)
        elif mode == "Thread":
            key = lambda e: str(as_list(e.meta.get("threads"))[0]) if as_list(e.meta.get("threads")) else ""
            cmap = color_map(key(s) for s in scenes)
        else:
            key = lambda e: e.tags[0] if e.tags else ""
            cmap = color_map(key(s) for s in scenes)
        self.canvas.color_of = lambda e: cmap.get(key(e), NONE_COLOR)
        used = {key(s) for s in scenes}
        shown = {k: v for k, v in cmap.items() if k in used or mode == "Status"}
        none_note = f"<span style='color:{NONE_COLOR}'>■</span>&nbsp;none" if "" in used and mode != "Status" else None
        lead = {"Tag": "Colored by first tag: ", "Thread": "Colored by first thread: "}.get(mode, "")
        self.legend.setText(lead + legend_html(shown, none_note))
        self.canvas.set_entries(entries)


# ============================================================================ matrix

class DotDelegate(QStyledItemDelegate):
    """Paints matrix cells: dot = present, ring = POV, tint = long absence."""

    def paint(self, p: QPainter, opt, index):
        data = index.data(PATH_ROLE + 1)
        if not data:
            return super().paint(p, opt, index)
        state, count, total, gap, color, dim = data
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        r = opt.rect
        if gap:
            p.fillRect(r, QColor(225, 87, 89, 46))
        if opt.state & opt.state.State_Selected:
            p.fillRect(r, QColor(opt.palette.highlight().color().red(), opt.palette.highlight().color().green(),
                                 opt.palette.highlight().color().blue(), 60))
        if dim:
            p.setOpacity(0.3)
        c = r.center()
        rad = min(r.height(), 22) // 2 - 4
        col = QColor(color)
        if state:
            p.setPen(Qt.NoPen)
            p.setBrush(col)
            p.drawEllipse(c, rad, rad)
            if state == 2:
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(col.lighter(150) if is_dark() else col.darker(150), 2))
                p.drawEllipse(c, rad + 3, rad + 3)
            if total > 1:
                f = QFont(opt.font)
                f.setPointSizeF(f.pointSizeF() * 0.8)
                p.setFont(f)
                p.setPen(opt.palette.text().color())
                p.drawText(QRect(c.x() + rad + 6, r.top(), r.right() - c.x() - rad - 6, r.height()),
                           Qt.AlignLeft | Qt.AlignVCenter, f"{count}/{total}")
        else:
            p.setPen(Qt.NoPen)
            p.setBrush(opt.palette.mid().color())
            p.drawEllipse(c, 1.5, 1.5)
        p.restore()

    def sizeHint(self, opt, index):
        return QSize(60, 28)


class MatrixView(QWidget):
    selected = Signal(object)
    opened = Signal(object)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.project: Project | None = None
        self.query = Query()
        self.row_items: list = []   # per row: (row entity, [scenes])
        self.columns: list[Entity] = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 0)
        bar = QHBoxLayout()
        bar.setContentsMargins(8, 0, 8, 0)
        self.rows = QComboBox()
        self.rows.addItems(["Chapters", "Scenes"])
        self.rows.setCurrentText(settings.value("matrix/rows", "Chapters", str))
        self.rows.currentTextChanged.connect(self._rows_changed)
        self.pick = QToolButton()
        self.pick.setText("Characters…")
        self.pick.setPopupMode(QToolButton.InstantPopup)
        self.pick_menu = QMenu(self.pick)
        self.pick.setMenu(self.pick_menu)
        self.gap = QSpinBox()
        self.gap.setRange(2, 99)
        self.gap.setValue(int(settings.value("matrix/gap", 5)))
        self.gap.setToolTip("Tint a character's absences once they run this long (after her first appearance).")
        self.gap.valueChanged.connect(self._gap_changed)
        for w in (_toolbar_label("Rows"), self.rows, self.pick, _toolbar_label("  Flag absences of"),
                  self.gap, _toolbar_label("rows or more")):
            bar.addWidget(w)
        bar.addStretch(1)
        self.filter_label = QLabel()
        self.filter_label.setStyleSheet("color: palette(highlight);")
        bar.addWidget(self.filter_label)
        lay.addLayout(bar)
        key = QLabel("● in the scene’s Characters   ◉ POV   "
                     "<span style='background:rgba(225,87,89,0.25)'>&nbsp;tinted&nbsp;</span> long absence   "
                     "Click a cell to select its scene, double-click to open it.")
        key.setTextFormat(Qt.RichText)
        key.setContentsMargins(10, 0, 10, 0)
        lay.addWidget(key)
        self.table = QTableWidget()
        self.table.setItemDelegate(DotDelegate(self.table))
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table.verticalHeader().setDefaultSectionSize(28)
        self.table.verticalHeader().setSectionsClickable(True)
        self.table.verticalHeader().sectionDoubleClicked.connect(self._row_header_dbl)
        self.table.verticalHeader().sectionClicked.connect(self._row_header_click)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setDefaultSectionSize(118)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignCenter)
        self.table.cellClicked.connect(self._cell_clicked)
        self.table.cellDoubleClicked.connect(self._cell_dbl)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        lay.addWidget(self.table, 1)

    def _rows_changed(self, t):
        self.settings.setValue("matrix/rows", t)
        self.refresh()

    def _gap_changed(self, v):
        self.settings.setValue("matrix/gap", v)
        self.refresh()

    def set_project(self, project):
        self.project = project

    def set_query(self, q: Query):
        self.query = q
        self.filter_label.setText(("Only scenes tagged " + " ".join("#" + t for t in q.tags)) if q.tags else "")

    # ------------------------------------------------------------ columns
    def _col_key(self):
        return f"matrix/cols/{project_key(self.project)}"

    def _default_columns(self, chars):
        lead = [c for c in chars if str(c.meta.get("role", "")).lower() in ("protagonist", "love interest")]
        return lead or chars

    def _selected_columns(self) -> list[Entity]:
        p = self.project
        chars = sorted(p.by_type("character"),
                       key=lambda c: ({"protagonist": 0, "love interest": 1}.get(
                           str(c.meta.get("role", "")).lower(), 2), natural_key(c.name)))
        saved = self.settings.value(self._col_key(), None)
        if saved is None:
            cols = self._default_columns(chars)
        else:
            names = {n.lower() for n in (saved if isinstance(saved, list) else [saved]) if n}
            cols = [c for c in chars if c.name.lower() in names]
        self.pick_menu.clear()
        for c in chars:
            a = self.pick_menu.addAction(c.name + (f"  ({c.meta.get('role')})" if c.meta.get("role") else ""))
            a.setCheckable(True)
            a.setChecked(c in cols)
            a.toggled.connect(lambda on, c=c: self._toggle_col(c, on))
        if chars:
            self.pick_menu.addSeparator()
            self.pick_menu.addAction("Protagonist + love interests").triggered.connect(self._reset_cols)
            self.pick_menu.addAction("Everyone").triggered.connect(
                lambda: self._set_cols([c.name for c in chars]))
        return cols

    def _toggle_col(self, c, on):
        names = [x.name for x in self.columns]
        if on and c.name not in names:
            names.append(c.name)
        elif not on:
            names = [n for n in names if n != c.name]
        self._set_cols(names)

    def _set_cols(self, names):
        self.settings.setValue(self._col_key(), list(names) if names else [""])
        self.refresh()

    def _reset_cols(self):
        self.settings.remove(self._col_key())
        self.refresh()

    # ------------------------------------------------------------ build
    @staticmethod
    def presence(scene: Entity, project: Project) -> dict:
        """Character path -> 2 for POV, 1 for listed in Characters."""
        out = {}
        for n in as_list(scene.meta.get("characters")):
            c = project.resolve(n)
            if c is not None:
                out[c.path] = 1
        if scene.meta.get("pov"):
            c = project.resolve(scene.meta.get("pov"))
            if c is not None:
                out[c.path] = 2
        return out

    def refresh(self):
        p = self.project
        if not p:
            return
        self.columns = self._selected_columns()
        q = self.query
        by_scene = self.rows.currentText() == "Scenes"
        rows = []
        if by_scene:
            for s in p.scenes_in_order():
                rows.append((s, [s]))
        else:
            for ch in p.chapters_in_order():
                rows.append((ch, [c for c in ch.children if c.type == "scene"]))
        if q.tags:
            rows = [(r, [s for s in ss if q.tag_match(s)]) for r, ss in rows]
            rows = [(r, ss) for r, ss in rows if ss]
        self.row_items = rows
        pres = {s.path: self.presence(s, p) for _, ss in rows for s in ss}
        colors = {c.path: PALETTE[i % len(PALETTE)] for i, c in enumerate(self.columns)}
        t = self.table
        t.clear()
        t.setRowCount(len(rows))
        t.setColumnCount(len(self.columns))
        unit = "scene" if by_scene else "ch"
        total_scenes = len({s.path for _, ss in rows for s in ss})
        for j, c in enumerate(self.columns):
            states = []
            for r, ss in rows:
                st = [pres[s.path].get(c.path, 0) for s in ss]
                states.append((max(st) if st else 0, sum(1 for x in st if x), len(ss)))
            present = [i for i, s in enumerate(states) if s[0]]
            gaps = set()
            longest, longest_at = 0, None
            if present:
                # rows with no scenes are neutral: they neither count as absence nor end one
                run = []
                for i in range(present[0], len(states) + 1):
                    if i < len(states) and states[i][2] == 0:
                        continue
                    if i < len(states) and not states[i][0]:
                        run.append(i)
                        continue
                    if len(run) > longest:
                        longest, longest_at = len(run), run[0]
                    if len(run) >= self.gap.value():
                        gaps.update(run)
                    run = []
            n_scenes = sum(s[1] for s in states)
            share = (100 * n_scenes / total_scenes) if total_scenes else 0
            head = f"{c.name}\n{n_scenes} scene{'s' if n_scenes != 1 else ''} · {share:.0f}%"
            head += f"\ngap {longest} {unit}" if longest else ("\nno gaps" if present else "\nnot on page")
            hi = QTableWidgetItem(head)
            tip = [f"<b>{c.name}</b>"]
            if c.meta.get("role"):
                tip.append(str(c.meta.get("role")))
            if present:
                tip.append(f"First appears: {self._row_name(rows[present[0]][0])}")
                if longest:
                    tip.append(f"Longest absence: {longest} {unit}, from {self._row_name(rows[longest_at][0])}")
            hi.setToolTip("<br>".join(tip))
            hi.setData(PATH_ROLE, str(c.path))
            t.setHorizontalHeaderItem(j, hi)
            for i, (state, count, tot) in enumerate(states):
                it = QTableWidgetItem()
                it.setData(PATH_ROLE + 1, (state, count, tot, i in gaps, colors[c.path], tot == 0))
                if state:
                    it.setToolTip(f"{c.name}: {'POV' if state == 2 else 'present'}"
                                  + (f" in {count} of {tot} scenes" if tot > 1 else ""))
                elif i in gaps:
                    it.setToolTip(f"{c.name} absent")
                t.setItem(i, j, it)
        for i, (r, ss) in enumerate(rows):
            label = r.name if by_scene else chapter_label(p, r)
            if not by_scene and len(ss) == 0:
                label += "  (no scenes)"
            vi = QTableWidgetItem(label)
            vi.setData(PATH_ROLE, str(r.path))
            if by_scene and r.parent is not None:
                vi.setToolTip(r.parent.name)
            t.setVerticalHeaderItem(i, vi)
        t.horizontalHeader().setMinimumHeight(t.fontMetrics().lineSpacing() * 3 + 12)
        if not self.columns:
            t.setColumnCount(1)
            t.setHorizontalHeaderItem(0, QTableWidgetItem("No characters selected — use Characters…"))
            t.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)

    def _row_name(self, e):
        return chapter_label(self.project, e) if e.type == "chapter" else e.name

    # ------------------------------------------------------------ clicks
    def _scenes_for(self, row, col):
        if not (0 <= row < len(self.row_items)):
            return [], None
        r, ss = self.row_items[row]
        if not (0 <= col < len(self.columns)):
            return ss, r
        c = self.columns[col]
        hits = [s for s in ss if c.path in self.presence(s, self.project)]
        return hits, r

    def _cell_clicked(self, row, col):
        hits, r = self._scenes_for(row, col)
        if len(hits) > 1:
            m = QMenu(self)
            for s in hits:
                m.addAction(s.name).triggered.connect(lambda *_, s=s: self.selected.emit(s.path))
            rect = self.table.visualRect(self.table.model().index(row, col))
            m.exec(self.table.viewport().mapToGlobal(rect.bottomLeft()))
        elif hits:
            self.selected.emit(hits[0].path)
        elif r is not None:
            self.selected.emit(r.path)

    def _cell_dbl(self, row, col):
        hits, r = self._scenes_for(row, col)
        target = hits[0] if hits else r
        if target is not None:
            self.opened.emit(target.path)

    def _row_header_click(self, row):
        if 0 <= row < len(self.row_items):
            self.selected.emit(self.row_items[row][0].path)

    def _row_header_dbl(self, row):
        if 0 <= row < len(self.row_items):
            self.opened.emit(self.row_items[row][0].path)
