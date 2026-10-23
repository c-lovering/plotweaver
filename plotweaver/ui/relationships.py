"""Editor field for a character's `relationships:` list."""
from __future__ import annotations

import re

import shiboken6
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (QComboBox, QFrame, QGridLayout, QLabel, QLineEdit, QPushButton,
                               QScrollArea, QSpinBox, QToolButton, QVBoxLayout, QWidget)

from ..model import REL_DIRECTED, REL_KEYS, REL_KINDS, as_list, make_link, strip_link
from .widgets import make_completer


_CH_NUM = re.compile(r"^(?:ch\.?\s*)?(\d+)$", re.I)


def _story_value(text: str):
    """since/until as typed: "4" or "ch. 4" is a chapter number, anything else is a link."""
    t = text.strip()
    if not t:
        return ""
    m = _CH_NUM.match(t)
    if m:
        return int(m.group(1))
    return make_link(t)


def _story_text(v) -> str:
    if v is None or v == "":
        return ""
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, (int, float)):
        return f"ch. {int(v)}"
    return strip_link(v)


class _Row:
    def __init__(self, owner: "RelationshipsEdit", entry: dict):
        self.entry = dict(entry)  # keeps any keys we don't edit
        self.frame = QFrame()
        self.frame.setFrameShape(QFrame.StyledPanel)
        g = QGridLayout(self.frame)
        g.setContentsMargins(6, 4, 4, 4)
        g.setHorizontalSpacing(6)
        g.setVerticalSpacing(4)
        self.with_ = QLineEdit(strip_link(entry.get("with")))
        self.with_.setPlaceholderText("With…")
        self.with_.setCompleter(owner.completer("chars", self.with_))
        self.kind = QComboBox()
        self.kind.setEditable(True)
        self.kind.addItems(REL_KINDS)
        self.kind.setCurrentText(str(entry.get("kind") or ""))
        self.kind.lineEdit().setPlaceholderText("Kind…")
        self.kind.setToolTip("Directed kinds read from this character: "
                             + ", ".join(f"{k} = “{v}”" for k, v in REL_DIRECTED.items())
                             + ". Anything else counts both ways. You can type your own.")
        self.intensity = QSpinBox()
        self.intensity.setRange(-1, 5)
        self.intensity.setPrefix("Intensity ")
        self.intensity.setSpecialValueText("Intensity —")
        self.intensity.setToolTip("0–5: how strong it is. Drawn as line thickness in the graph.")
        try:
            self.intensity.setValue(max(0, min(5, int(entry.get("intensity")))))
        except (TypeError, ValueError):
            self.intensity.setValue(-1)
        self.remove = QToolButton()
        self.remove.setText("✕")
        self.remove.setToolTip("Remove this relationship")
        self.since = QLineEdit(_story_text(entry.get("since")))
        self.since.setPlaceholderText("Since (chapter/scene)")
        self.since.setCompleter(owner.completer("story", self.since))
        self.since.setToolTip("When it starts: a chapter or scene name, or a chapter number like 4. "
                              "Empty = from the start.")
        self.until = QLineEdit(_story_text(entry.get("until")))
        self.until.setPlaceholderText("Until")
        self.until.setCompleter(owner.completer("story", self.until))
        self.until.setToolTip("When it ends (it no longer holds from here). To show it changing, "
                              "add another entry for what it becomes, starting at the same point.")
        self.note = QLineEdit(str(entry.get("note") or ""))
        self.note.setPlaceholderText("Note")
        g.addWidget(self.with_, 0, 0)
        g.addWidget(self.kind, 0, 1)
        g.addWidget(self.intensity, 0, 2)
        g.addWidget(self.remove, 0, 3)
        g.addWidget(self.since, 1, 0)
        g.addWidget(self.until, 1, 1)
        g.addWidget(self.note, 1, 2, 1, 2)
        g.setColumnStretch(0, 3)
        g.setColumnStretch(1, 2)
        g.setColumnStretch(2, 2)
        for w in (self.with_, self.since, self.until, self.note):
            w.textEdited.connect(owner.changed)
        for w in (self.with_.completer(), self.since.completer(), self.until.completer()):
            w.activated.connect(lambda *_: owner.changed.emit())
        self.kind.currentTextChanged.connect(owner.changed)
        self.intensity.valueChanged.connect(owner.changed)
        self.remove.clicked.connect(lambda: owner.remove_row(self))

    def value(self) -> dict | None:
        who = self.with_.text().strip()
        if not who:
            return None
        out = {k: v for k, v in self.entry.items() if k not in REL_KEYS}
        vals = {"with": make_link(who), "kind": self.kind.currentText().strip(),
                "intensity": self.intensity.value() if self.intensity.value() >= 0 else None,
                "since": _story_value(self.since.text()), "until": _story_value(self.until.text()),
                "note": self.note.text().strip()}
        ordered = {k: vals[k] for k in REL_KEYS if vals[k] not in (None, "")}
        ordered.update(out)
        return ordered


class RelationshipsEdit(QWidget):
    """A list of relationship entries, plus the ones other characters' notes hold about this one."""
    changed = Signal()
    follow = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows: list[_Row] = []
        self._chars: list[str] = []
        self._story: list[str] = []
        self._completers = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        inner = QWidget()
        self.box = QVBoxLayout(inner)
        self.box.setContentsMargins(0, 0, 0, 0)
        self.box.setSpacing(4)
        self.scroll = QScrollArea()
        self.scroll.setWidget(inner)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.hide()
        lay.addWidget(self.scroll)
        self.add = QPushButton("Add relationship")
        self.add.setToolTip("Each relationship belongs to the pair. Write it on either character; "
                            "the other's note lists it below its own.")
        self.add.clicked.connect(self._add_clicked)
        lay.addWidget(self.add, 0, Qt.AlignLeft)
        self.incoming = QLabel()
        self.incoming.setWordWrap(True)
        self.incoming.setTextFormat(Qt.RichText)
        self.incoming.setStyleSheet("color: palette(placeholder-text);")
        self.incoming.linkActivated.connect(self.follow)
        self.incoming.hide()
        lay.addWidget(self.incoming)

    # ------------------------------------------------------------ completers
    def completer(self, kind: str, line: QLineEdit):
        c = make_completer(line)  # owned by the line edit, so it goes when the row does
        c.model().setStringList(self._chars if kind == "chars" else self._story)
        self._completers.append((kind, c))
        return c

    def set_options(self, chars, story):
        self._chars, self._story = list(chars), list(story)
        self._completers = [(k, c) for k, c in self._completers if shiboken6.isValid(c)]
        for kind, c in self._completers:
            c.model().setStringList(self._chars if kind == "chars" else self._story)

    # ------------------------------------------------------------ rows
    def _add_row(self, entry: dict) -> _Row:
        r = _Row(self, entry)
        self.rows.append(r)
        self.box.addWidget(r.frame)
        self._fit()
        return r

    MAX_HEIGHT = 200  # about two and a half entries; the rest scrolls

    def _fit(self):
        QTimer.singleShot(0, self._fit_now)

    def _fit_now(self):
        if not shiboken6.isValid(self):
            return
        self.scroll.setVisible(bool(self.rows))
        h = self.scroll.widget().sizeHint().height()
        self.scroll.setFixedHeight(min(h, self.MAX_HEIGHT))

    def _add_clicked(self):
        r = self._add_row({})
        r.with_.setFocus()
        QTimer.singleShot(50, lambda: shiboken6.isValid(r.frame) and self.scroll.ensureWidgetVisible(r.frame))

    def remove_row(self, r: _Row):
        self.rows.remove(r)
        r.frame.setParent(None)
        r.frame.deleteLater()
        self._fit()
        self.changed.emit()

    def set_value(self, v):
        for r in self.rows:
            r.frame.setParent(None)
            r.frame.deleteLater()
        self.rows = []
        for entry in as_list(v):
            if isinstance(entry, dict):
                self._add_row(entry)
        self._fit()

    def value(self) -> list:
        return [x for x in (r.value() for r in self.rows) if x]

    def set_incoming(self, rels):
        """Relationships about this character that live on other notes."""
        if not rels:
            self.incoming.hide()
            return
        lines = []
        for r in rels:
            name = r.holder.name.replace("&", "&amp;").replace("<", "&lt;")
            bits = [r.kind or "related"]
            if r.intensity is not None:
                bits.append(f"intensity {r.intensity}")
            if r.since:
                bits.append("since " + _story_text(r.since))
            if r.until:
                bits.append("until " + _story_text(r.until))
            what = REL_DIRECTED.get(r.kind.lower())
            label = f"{name} {what} them" if what else f"{name}: {bits[0]}"
            rest = ", ".join(bits[1:])
            lines.append(f"<a href='{name}'>{label}</a>" + (f" ({rest})" if rest else ""))
        self.incoming.setText("On other notes: " + " · ".join(lines))
        self.incoming.show()
