"""Relationship graph: characters as nodes, relationships as links, over story time."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (QColor, QFont, QFontMetrics, QPainter, QPainterPath,
                           QPainterPathStroker, QPen, QPixmap, QPolygonF)
from PySide6.QtWidgets import (QCheckBox, QComboBox, QHBoxLayout, QLabel, QMenu, QSlider,
                               QToolButton, QToolTip, QVBoxLayout, QWidget)

from ..model import REL_DIRECTED, REL_KINDS, Entity, Project, Query, natural_key, strip_link
from .theme import accent, muted
from .views import PALETTE, chapter_label, project_key

KIND_COLORS = {"lover": "#e15759", "attraction": "#ff9da7", "harem sister": "#a463f2",
               "friend": "#59a14f", "family": "#9c755f", "ally": "#4e79a7", "rival": "#f28e2b",
               "enemy": "#bcbd22", "mentor": "#76b7b2", "serves": "#9edae5"}
ROLE_COLORS = {"protagonist": "#f2c14e", "love interest": "#e86a92", "antagonist": "#9b6bd6"}
OTHER_ROLE = "#8e9096"
NODE_R = 24
MODES = ["Harem", "Everyone in a relationship", "All characters"]


def kind_color(kind: str) -> str:
    k = kind.lower()
    if k in KIND_COLORS:
        return KIND_COLORS[k]
    return PALETTE[sum(map(ord, k)) % len(PALETTE)] if k else OTHER_ROLE


def role_of(e: Entity) -> str:
    return str(e.meta.get("role") or "").strip().lower()


def story_text(v) -> str:
    return f"ch. {int(v)}" if isinstance(v, (int, float)) and not isinstance(v, bool) else strip_link(v)


@dataclass(eq=False)
class Node:
    e: Entity
    pos: QPointF          # layout coordinates: center (0, 0), ring of radius 1 fits the view
    color: str
    pixmap: QPixmap | None = None
    tip: str = ""


@dataclass(eq=False)
class Edge:
    a: Node
    b: Node
    color: str
    width: float
    directed: bool = False
    dashed: bool = False   # ended before this point in the story
    dotted: bool = False   # no relationship, they only share scenes
    label: str = ""
    tip: str = ""
    target: object = None  # path to select when clicked
    bend: float = 0.0      # set by the canvas when a pair has several links
    path: QPainterPath = field(default_factory=QPainterPath)


class GraphCanvas(QWidget):
    selected = Signal(object)
    opened = Signal(object)
    moved = Signal(object)    # {name: (x, y)} after a drag

    def __init__(self, parent=None):
        super().__init__(parent)
        self.nodes: list[Node] = []
        self.edges: list[Edge] = []
        self.message = ""
        self.current = None
        self._hover = None       # Node or Edge
        self._drag: Node | None = None
        self._drag_moved = False
        self.setMouseTracking(True)
        self.setMinimumSize(320, 280)

    def set_data(self, nodes, edges, message=""):
        self.nodes, self.edges, self.message = nodes, edges, message
        self._hover = None
        groups: dict[frozenset, list[Edge]] = {}
        for ed in edges:
            groups.setdefault(frozenset((id(ed.a), id(ed.b))), []).append(ed)
        for grp in groups.values():
            n = len(grp)
            for i, ed in enumerate(grp):
                off = i - (n - 1) / 2
                # keep a consistent side whichever way round the edge was stored
                flip = -1 if str(ed.a.e.path) > str(ed.b.e.path) else 1
                ed.bend = off * flip
        self.update()

    # ------------------------------------------------------------ geometry
    LABEL_ROOM = 22  # name label under each node

    def _scale(self) -> float:
        usable = min(self.width() - 2 * 70, self.height() - self.LABEL_ROOM - 2 * 12)
        return max(40.0, usable / 2 - NODE_R)

    def _center(self) -> QPointF:
        return QPointF(self.width() / 2, (self.height() - self.LABEL_ROOM) / 2)

    def to_screen(self, p: QPointF) -> QPointF:
        s, c = self._scale(), self._center()
        return QPointF(c.x() + p.x() * s, c.y() + p.y() * s)

    def to_layout(self, p: QPointF) -> QPointF:
        s, c = self._scale(), self._center()
        x = (p.x() - c.x()) / s
        y = (p.y() - c.y()) / s
        return QPointF(max(-1.0, min(1.0, x)), max(-1.0, min(1.0, y)))

    def _edge_geometry(self, ed: Edge):
        pa, pb = self.to_screen(ed.a.pos), self.to_screen(ed.b.pos)
        mid = (pa + pb) / 2
        d = pb - pa
        ln = math.hypot(d.x(), d.y()) or 1.0
        normal = QPointF(-d.y() / ln, d.x() / ln)
        ctrl = mid + normal * (ed.bend * 34)
        path = QPainterPath(pa)
        path.quadTo(ctrl, pb)
        return pa, pb, ctrl, path

    def node_at(self, pos) -> Node | None:
        for n in reversed(self.nodes):
            c = self.to_screen(n.pos)
            if math.hypot(c.x() - pos.x(), c.y() - pos.y()) <= NODE_R + 2:
                return n
        return None

    def edge_at(self, pos) -> Edge | None:
        st = QPainterPathStroker()
        st.setWidth(10)
        for ed in reversed(self.edges):
            if st.createStroke(ed.path).contains(QPointF(pos)):
                return ed
        return None

    # ------------------------------------------------------------ paint
    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pal = self.palette()
        p.fillRect(self.rect(), pal.base())
        if not self.nodes:
            p.setPen(muted(pal))
            p.drawText(self.rect().adjusted(40, 40, -40, -40), Qt.AlignCenter | Qt.TextWordWrap,
                       self.message or "No characters to show.")
            return
        focus = self._hover if isinstance(self._hover, Node) else None
        hover_edge = self._hover if isinstance(self._hover, Edge) else None
        for ed in self.edges:
            pa, pb, ctrl, path = self._edge_geometry(ed)
            ed.path = path
            col = QColor(ed.color)
            faded = focus is not None and focus not in (ed.a, ed.b)
            if ed.dotted:
                col = QColor(muted(pal))
            alpha = 255
            if ed.dashed:
                alpha = 120
            if ed.dotted:
                alpha = 150
            if faded:
                alpha = 35
            col.setAlpha(alpha)
            w = ed.width + (1.5 if ed is hover_edge else 0)
            pen = QPen(col, w, Qt.SolidLine, Qt.RoundCap)
            if ed.dashed:
                pen.setStyle(Qt.DashLine)
            elif ed.dotted:
                pen.setStyle(Qt.DotLine)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)
            if ed.directed:
                self._arrow(p, path, col, w)
        # labels after all lines so they sit on top
        f = QFont(self.font())
        f.setPointSizeF(f.pointSizeF() * 0.85)
        p.setFont(f)
        fm = QFontMetrics(f)
        for ed in self.edges:
            if not ed.label:
                continue
            if focus is not None and focus not in (ed.a, ed.b):
                continue
            pt = ed.path.pointAtPercent(0.5)
            w = fm.horizontalAdvance(ed.label) + 10
            r = QRectF(pt.x() - w / 2, pt.y() - fm.height() / 2 - 1, w, fm.height() + 2)
            warn = ed.label.startswith("0 ")
            p.setPen(QPen(QColor(accent("missing")) if warn else
                          QColor(ed.color) if not ed.dotted else muted(pal), 1))
            p.setBrush(pal.base())
            p.drawRoundedRect(r, 8, 8)
            p.setPen(QColor(accent("missing")) if warn else pal.text().color())
            p.drawText(r, Qt.AlignCenter, ed.label)
        self._paint_nodes(p, focus)

    @staticmethod
    def _arrow(p, path, col, width):
        """Arrowhead two-thirds along the line, pointing at the target (clear of labels)."""
        size = 7 + width
        tip = path.pointAtPercent(0.68)
        back = path.pointAtPercent(0.6)
        d = tip - back
        ln = math.hypot(d.x(), d.y()) or 1.0
        u = QPointF(d.x() / ln, d.y() / ln)
        tip = tip + u * (size / 2)
        left = tip - u * size + QPointF(-u.y(), u.x()) * (size * 0.55)
        right = tip - u * size - QPointF(-u.y(), u.x()) * (size * 0.55)
        p.setPen(Qt.NoPen)
        p.setBrush(col)
        p.drawPolygon(QPolygonF([tip, left, right]))

    def _paint_nodes(self, p, focus):
        pal = self.palette()
        f = QFont(self.font())
        bold = QFont(f)
        bold.setBold(True)
        fm = QFontMetrics(f)
        linked = set()
        if focus is not None:
            for ed in self.edges:
                if focus in (ed.a, ed.b):
                    linked.update((ed.a, ed.b))
        for n in self.nodes:
            c = self.to_screen(n.pos)
            r = QRectF(c.x() - NODE_R, c.y() - NODE_R, NODE_R * 2, NODE_R * 2)
            faded = focus is not None and n not in linked and n is not focus
            p.setOpacity(0.35 if faded else 1.0)
            ring = QColor(n.color)
            p.setPen(Qt.NoPen)
            p.setBrush(pal.button())
            p.drawEllipse(r)
            if n.pixmap is not None and not n.pixmap.isNull():
                clip = QPainterPath()
                clip.addEllipse(r)
                p.save()
                p.setClipPath(clip)
                pm = n.pixmap
                side = min(pm.width(), pm.height())
                src = QRectF((pm.width() - side) / 2, 0 if pm.height() > pm.width() else (pm.height() - side) / 2,
                             side, side)
                p.drawPixmap(r, pm, src)
                p.restore()
            else:
                p.setFont(bold)
                p.setPen(pal.text().color())
                initials = "".join(w[0] for w in n.e.name.split()[:2]).upper()
                p.drawText(r, Qt.AlignCenter, initials)
            sel = self.current is not None and n.e.path == self.current
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(pal.highlight().color() if sel else ring, 4 if sel else 3))
            p.drawEllipse(r)
            p.setFont(f)
            tw = fm.horizontalAdvance(n.e.name) + 8
            tr = QRectF(c.x() - tw / 2, r.bottom() + 3, tw, fm.height() + 2)
            bg = QColor(pal.base().color())
            bg.setAlpha(210)
            p.setPen(Qt.NoPen)
            p.setBrush(bg)
            p.drawRoundedRect(tr, 4, 4)
            p.setPen(pal.text().color())
            p.drawText(tr, Qt.AlignCenter, n.e.name)
        p.setOpacity(1.0)

    # ------------------------------------------------------------ mouse
    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        n = self.node_at(e.position())
        self._drag, self._drag_moved = n, False
        if n is None:
            ed = self.edge_at(e.position())
            if ed is not None and ed.target is not None:
                self.selected.emit(ed.target)

    def mouseMoveEvent(self, e):
        pos = e.position()
        if self._drag is not None and e.buttons() & Qt.LeftButton:
            self._drag.pos = self.to_layout(pos)
            self._drag_moved = True
            self.update()
            return
        hit = self.node_at(pos) or self.edge_at(pos)
        if hit is not self._hover:
            self._hover = hit
            self.update()
            tip = ""
            if isinstance(hit, Node):
                tip = hit.tip
            elif isinstance(hit, Edge):
                tip = hit.tip
            if tip:
                QToolTip.showText(e.globalPosition().toPoint(), tip, self)
            else:
                QToolTip.hideText()
        self.setCursor(Qt.PointingHandCursor if hit is not None else Qt.ArrowCursor)

    def mouseReleaseEvent(self, e):
        n, self._drag = self._drag, None
        if n is None:
            return
        if self._drag_moved:
            self.moved.emit({x.e.name: (round(x.pos.x(), 4), round(x.pos.y(), 4)) for x in self.nodes})
        else:
            self.selected.emit(n.e.path)

    def mouseDoubleClickEvent(self, e):
        n = self.node_at(e.position())
        if n is not None:
            self.opened.emit(n.e.path)
            return
        ed = self.edge_at(e.position())
        if ed is not None and ed.target is not None:
            self.opened.emit(ed.target)

    def leaveEvent(self, e):
        if self._hover is not None:
            self._hover = None
            self.update()


class GraphView(QWidget):
    selected = Signal(object)
    opened = Signal(object)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.project: Project | None = None
        self.query = Query()
        self._pix: dict = {}
        self._chapters_seen = -1
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 0)
        bar = QHBoxLayout()
        bar.setContentsMargins(8, 0, 8, 0)
        self.mode = QComboBox()
        self.mode.addItems(MODES)
        self.mode.setCurrentText(settings.value("graph/mode", MODES[0], str))
        self.mode.setToolTip("Harem: the protagonist in the middle and love interests on the ring, "
                             "with only the links between them.")
        self.mode.currentTextChanged.connect(lambda t: (self.settings.setValue("graph/mode", t), self.refresh()))
        self.kinds_btn = QToolButton()
        self.kinds_btn.setText("Kinds…")
        self.kinds_btn.setPopupMode(QToolButton.InstantPopup)
        self.kinds_menu = QMenu(self.kinds_btn)
        self.kinds_btn.setMenu(self.kinds_menu)
        self.ended = self._check("Ended", "graph/ended", True,
                                 "Show relationships that have ended by this chapter as dashed lines.")
        self.counts = self._check("Scene counts", "graph/counts", True,
                                  "Label each link with how many scenes the pair share up to this chapter.")
        self.unlinked = self._check("Unlinked pairs", "graph/unlinked", True,
                                    "Dotted lines between characters who share scenes but have no "
                                    "relationship written down yet.")
        self.reset = QToolButton()
        self.reset.setText("Reset layout")
        self.reset.clicked.connect(self._reset_layout)
        for w in (QLabel("Show"), self.mode, self.kinds_btn, self.ended, self.counts, self.unlinked, self.reset):
            bar.addWidget(w)
        bar.addStretch(1)
        self.filter_label = QLabel()
        self.filter_label.setStyleSheet("color: palette(highlight);")
        bar.addWidget(self.filter_label)
        lay.addLayout(bar)

        tl = QHBoxLayout()
        tl.setContentsMargins(8, 0, 8, 0)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setPageStep(1)
        self.slider.setTickPosition(QSlider.TicksBelow)
        self.slider.valueChanged.connect(lambda *_: self.refresh())
        self.when = QLabel()
        self.when.setMinimumWidth(220)
        tl.addWidget(QLabel("As of"))
        tl.addWidget(self.slider, 1)
        tl.addWidget(self.when)
        lay.addLayout(tl)

        self.legend = QLabel()
        self.legend.setTextFormat(Qt.RichText)
        self.legend.setWordWrap(True)
        self.legend.setContentsMargins(10, 0, 10, 0)
        lay.addWidget(self.legend)
        self.canvas = GraphCanvas()
        self.canvas.selected.connect(self.selected)
        self.canvas.opened.connect(self.opened)
        self.canvas.moved.connect(self._save_layout)
        lay.addWidget(self.canvas, 1)

    def _check(self, text, key, default, tip):
        c = QCheckBox(text)
        c.setChecked(self.settings.value(key, default, bool))
        c.setToolTip(tip)
        c.toggled.connect(lambda on: (self.settings.setValue(key, on), self.refresh()))
        return c

    def set_project(self, project):
        self.project = project
        self._pix = {}
        self._chapters_seen = -1

    def set_query(self, q: Query):
        self.query = q
        self.filter_label.setText(("Scene counts only from scenes tagged " + " ".join("#" + t for t in q.tags))
                                  if q.tags else "")

    def set_current(self, path):
        self.canvas.current = path
        self.canvas.update()

    # ------------------------------------------------------------ settings
    def _layout_key(self):
        return f"graph/pos/{project_key(self.project)}/{self.mode.currentIndex()}"

    def _saved_layout(self) -> dict:
        raw = self.settings.value(self._layout_key(), "", str)
        try:
            data = json.loads(raw) if raw else {}
        except ValueError:
            data = {}
        return {k.lower(): v for k, v in data.items()} if isinstance(data, dict) else {}

    def _save_layout(self, positions):
        self.settings.setValue(self._layout_key(), json.dumps(positions))

    def _reset_layout(self):
        self.settings.remove(self._layout_key())
        self.refresh()

    def _hidden_kinds(self) -> set:
        v = self.settings.value("graph/hidden_kinds", [], list) or []
        return {str(x).lower() for x in (v if isinstance(v, list) else [v]) if x}

    def _toggle_kind(self, kind, on):
        hidden = self._hidden_kinds()
        (hidden.discard if on else hidden.add)(kind.lower())
        self.settings.setValue("graph/hidden_kinds", sorted(hidden) or [""])
        self.refresh()

    def _fill_kinds(self, kinds):
        hidden = self._hidden_kinds()
        self.kinds_menu.clear()
        for k in kinds:
            a = self.kinds_menu.addAction(k)
            a.setCheckable(True)
            a.setChecked(k.lower() not in hidden)
            a.toggled.connect(lambda on, k=k: self._toggle_kind(k, on))
        self.kinds_btn.setText("Kinds…" if not hidden else f"Kinds ({len(hidden)} hidden)…")

    def _pixmap(self, e: Entity):
        v = e.meta.get("portrait")
        path = self.project.image_path(v) if v else None
        if path is None or not path.exists():
            return None
        key = (str(path), path.stat().st_mtime)
        if key not in self._pix:
            pm = QPixmap(str(path))
            if not pm.isNull():
                pm = pm.scaled(NODE_R * 4, NODE_R * 4, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            self._pix[key] = pm
        return self._pix[key]

    # ------------------------------------------------------------ build
    def _default_positions(self, groups) -> dict:
        """Protagonist(s) in the middle, love interests on the ring, everyone else outside."""
        out = {}
        center, ring, outer = groups
        if len(center) == 1:
            out[center[0].path] = (0.0, 0.0)
        for i, c in enumerate(center if len(center) > 1 else []):
            a = -math.pi / 2 + 2 * math.pi * i / len(center)
            out[c.path] = (0.2 * math.cos(a), 0.2 * math.sin(a))
        r1 = 0.58 if outer else 0.9
        for i, c in enumerate(ring):
            a = -math.pi / 2 + 2 * math.pi * i / len(ring)
            out[c.path] = (r1 * math.cos(a), r1 * math.sin(a))
        for i, c in enumerate(outer):
            a = -math.pi / 2 + math.pi / max(1, len(outer)) + 2 * math.pi * i / len(outer)
            out[c.path] = (math.cos(a), math.sin(a))
        return out

    def refresh(self):
        p = self.project
        if not p:
            return
        chars = p.by_type("character")
        rels, missing = p.relationships()
        chapters = p.chapters_in_order()

        # timeline: stay on the last chapter if that's where the slider was
        n = len(chapters)
        if n != self._chapters_seen:
            at_end = self.slider.value() >= self.slider.maximum() or self._chapters_seen < 0
            self.slider.blockSignals(True)
            self.slider.setRange(0, max(0, n - 1))
            if at_end:
                self.slider.setValue(max(0, n - 1))
            self.slider.blockSignals(False)
            self._chapters_seen = n
        self.slider.setEnabled(n > 1)
        at = self.slider.value() if n else None
        if n:
            label = chapter_label(p, chapters[at])
            self.when.setText(f"<b>{label}</b>  ({at + 1} of {n})")
        else:
            self.when.setText("no chapters yet (timing ignored)")

        # first appearance, for a story-order ring
        first = {}
        for i, s in enumerate(p.scenes_in_order()):
            for c in p.scene_cast(s):
                first.setdefault(c, i)

        def story_order(c):
            return (first.get(c.path, 1e9), natural_key(c.name))

        protagonists = [c for c in chars if role_of(c) == "protagonist"]
        interests = [c for c in chars if role_of(c) == "love interest"]
        harem = set(protagonists) | set(interests)
        hidden_kinds = self._hidden_kinds()
        kinds = list(REL_KINDS) + sorted({r.kind for r in rels if r.kind and r.kind.lower() not in REL_KINDS},
                                         key=natural_key)
        self._fill_kinds(kinds)

        mode = self.mode.currentIndex()
        shown = []
        for r in rels:
            if r.kind.lower() in hidden_kinds:
                continue
            state = p.rel_state(r, at)
            if state == "future" or (state == "ended" and not self.ended.isChecked()):
                continue
            shown.append((r, state))
        if mode == 0:
            nodes_e = harem
        elif mode == 1:
            nodes_e = set(harem)
            for r, _ in shown:
                nodes_e.update((r.holder, r.other))
        else:
            nodes_e = set(chars)
        shown = [(r, st) for r, st in shown if r.holder in nodes_e and r.other in nodes_e]

        center = sorted((c for c in nodes_e if c in protagonists), key=story_order)
        ring = sorted((c for c in nodes_e if c in interests and c not in protagonists), key=story_order)
        outer = sorted((c for c in nodes_e if c not in harem), key=story_order)
        defaults = self._default_positions((center, ring, outer))
        saved = self._saved_layout()
        nodes = {}
        for c in center + ring + outer:
            xy = saved.get(c.name.lower()) or defaults[c.path]
            nd = Node(c, QPointF(float(xy[0]), float(xy[1])), ROLE_COLORS.get(role_of(c), OTHER_ROLE),
                      self._pixmap(c))
            nodes[c.path] = nd

        shared = p.shared_scenes(at, self.query) if (self.counts.isChecked() or self.unlinked.isChecked()) else {}
        edges, labelled, linked_pairs = [], set(), set()
        for r, state in shown:
            pair = r.pair()
            linked_pairs.add(pair)
            cnt = shared.get(pair, 0)
            lab = ""
            if self.counts.isChecked() and pair not in labelled:
                lab = f"{cnt} scene{'s' if cnt != 1 else ''}"
                labelled.add(pair)
            width = 1.5 + 1.1 * (r.intensity if r.intensity is not None else 1)
            edges.append(Edge(nodes[r.holder.path], nodes[r.other.path], kind_color(r.kind), width,
                              directed=r.directed, dashed=state == "ended", label=lab,
                              tip=self._rel_tip(r, state, cnt), target=r.holder.path))
        if self.unlinked.isChecked():
            items = list(nodes.values())
            for i, a in enumerate(items):
                for b in items[i + 1:]:
                    pair = frozenset((a.e.path, b.e.path))
                    cnt = shared.get(pair, 0)
                    if cnt and pair not in linked_pairs:
                        edges.append(Edge(a, b, OTHER_ROLE, 1.2, dotted=True,
                                          label=f"{cnt}" if self.counts.isChecked() else "",
                                          tip=f"<b>{a.e.name} & {b.e.name}</b><br>"
                                              f"Share {cnt} scene{'s' if cnt != 1 else ''} so far, "
                                              "but no relationship is written down."))

        # node tooltips
        per_char = {}
        for r, _ in shown:
            per_char[r.holder.path] = per_char.get(r.holder.path, 0) + 1
            per_char[r.other.path] = per_char.get(r.other.path, 0) + 1
        for nd in nodes.values():
            tip = [f"<b>{nd.e.name}</b>"]
            if nd.e.meta.get("role"):
                tip.append(str(nd.e.meta.get("role")))
            tip.append(f"{per_char.get(nd.e.path, 0)} relationship(s) shown")
            nd.tip = "<br>".join(tip)
        msg = ""
        if not chars:
            msg = "No characters yet. Add some, then give them relationships on their notes."
        elif not nodes:
            msg = ("Harem view needs a character with the role “protagonist” or “love interest”. "
                   "Switch Show to “All characters”, or set roles on the character notes.")
        self.canvas.set_data(list(nodes.values()), edges, msg)
        self._legend(kinds, shown, missing, rels)

    def _rel_tip(self, r, state, cnt) -> str:
        lines = [f"<b>{r.describe()}</b>"]
        if r.intensity is not None:
            lines.append(f"Intensity {r.intensity} of 5")
        when = []
        if r.since:
            when.append("since " + story_text(r.since))
        if r.until:
            when.append(("ended " if state == "ended" else "until ") + story_text(r.until))
        if when:
            lines.append(", ".join(when))
        if r.note:
            lines.append(r.note.replace("<", "&lt;"))
        lines.append(f"{cnt} shared scene{'s' if cnt != 1 else ''} so far")
        lines.append(f"<i>On {r.holder.name}’s note. Click to open it.</i>")
        return "<br>".join(lines)

    def _legend(self, kinds, shown, missing, rels):
        used = {r.kind.lower() for r, _ in shown}
        chips = [f"<span style='color:{kind_color(k)}'>━</span>&nbsp;{k}"
                 + ("&nbsp;→" if k.lower() in REL_DIRECTED else "")
                 for k in kinds if k.lower() in used]
        text = "&nbsp;&nbsp;&nbsp;".join(chips) if chips else ""
        hints = ["thicker = more intense", "dashed = ended", "dotted = share scenes, no relationship",
                 "<span style='color:%s'>0 scenes</span> = never on page together" % accent("missing"),
                 "drag to rearrange"]
        text += ("&nbsp;&nbsp;&nbsp;" if text else "") + f"<span style='color:{muted(self.palette()).name()}'>" \
            + " · ".join(hints) + "</span>"
        if not rels:
            text += "<br>No relationships yet. Add them under <b>Relationships</b> on a character's note."
        if missing:
            text += ("<br><span style='color:#e15759'>Relationships with no character note: "
                     + ", ".join(m.replace("<", "&lt;") for m in missing) + "</span>")
        self.legend.setText(text)
