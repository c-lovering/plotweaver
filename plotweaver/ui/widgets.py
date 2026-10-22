"""Reusable input widgets: link fields, comma lists, the wikilink-aware notes editor."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, QStringListModel, Qt, Signal
from PySide6.QtGui import (QColor, QFont, QPainter, QPixmap, QIcon, QSyntaxHighlighter,
                           QTextCharFormat, QTextCursor)
from PySide6.QtWidgets import (QCompleter, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
                               QPushButton, QToolButton, QWidget)

from ..model import LINK_RE, as_list, make_link, strip_link

STATUS_COLORS = {"idea": "#9aa0a6", "outlined": "#4a90d9", "drafted": "#e6a23c",
                 "revised": "#9b59b6", "done": "#3fae5a"}
_icon_cache: dict[str, QIcon] = {}


def status_icon(status: str) -> QIcon:
    status = status or "idea"
    if status not in _icon_cache:
        pm = QPixmap(14, 14)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(STATUS_COLORS.get(status, "#9aa0a6")))
        p.drawEllipse(2, 2, 10, 10)
        p.end()
        _icon_cache[status] = QIcon(pm)
    return _icon_cache[status]


def make_completer(parent, cls=QCompleter) -> QCompleter:
    c = cls(parent)
    c.setModel(QStringListModel(c))
    c.setCaseSensitivity(Qt.CaseInsensitive)
    c.setFilterMode(Qt.MatchContains)
    c.setCompletionMode(QCompleter.PopupCompletion)
    c.setMaxVisibleItems(12)
    return c


class LinkEdit(QWidget):
    """A single [[link]] to another note, with autocomplete and a jump button."""
    changed = Signal()
    follow = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.line = QLineEdit()
        self.line.setPlaceholderText("Type a name…")
        self.completer = make_completer(self.line)
        self.line.setCompleter(self.completer)
        self.go = QToolButton()
        self.go.setText("→")
        self.go.setToolTip("Open this note")
        lay.addWidget(self.line, 1)
        lay.addWidget(self.go)
        self.line.textEdited.connect(self.changed)
        self.completer.activated.connect(lambda *_: self.changed.emit())
        self.go.clicked.connect(lambda: self.line.text().strip() and self.follow.emit(self.line.text()))

    def set_options(self, names):
        self.completer.model().setStringList(list(names))

    def value(self) -> str:
        return make_link(self.line.text())

    def set_value(self, v):
        self.line.setText(strip_link(v) if v else "")


class _MultiCompleter(QCompleter):
    def splitPath(self, path):
        return [path.split(",")[-1].strip()]

    def pathFromIndex(self, index):
        text = super().pathFromIndex(index)
        parts = self.widget().text().split(",")
        if len(parts) > 1:
            return ", ".join(p.strip() for p in parts[:-1]) + ", " + text
        return text


class ListEdit(QLineEdit):
    """Comma-separated values; stored as a YAML list (of [[links]] when links=True)."""
    changed = Signal()

    def __init__(self, links=False, placeholder="", parent=None, strip_hash=False):
        super().__init__(parent)
        self.links = links
        self.strip_hash = strip_hash
        self.setPlaceholderText(placeholder or "Comma-separated…")
        self.completer_ = make_completer(self, _MultiCompleter)
        self.setCompleter(self.completer_)
        self.textEdited.connect(self.changed)
        self.completer_.activated.connect(lambda *_: self.changed.emit())

    def set_options(self, names):
        self.completer_.model().setStringList(list(names))

    def items(self) -> list[str]:
        out = []
        for part in self.text().split(","):
            part = strip_link(part) if self.links else part.strip()
            if self.strip_hash:
                part = part.lstrip("#").strip()
            if part and part not in out:
                out.append(part)
        return out

    def value(self) -> list:
        items = self.items()
        return [make_link(i) for i in items] if self.links else items

    def set_value(self, v):
        vals = as_list(v)
        self.setText(", ".join(strip_link(x) if self.links else str(x) for x in vals))


class ProseField(QWidget):
    """Path to a draft written elsewhere (e.g. FocusWriter) plus its word count."""
    changed = Signal()
    browse = Signal()
    create = Signal()
    open = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.line = QLineEdit()
        self.line.setPlaceholderText("No draft linked")
        self.words = QLabel("")
        self.words.setMinimumWidth(80)
        b_browse, b_new, self.b_open = QPushButton("Link…"), QPushButton("New…"), QPushButton("Open")
        b_browse.setToolTip("Link an existing draft file")
        b_new.setToolTip("Create a new empty draft file and link it")
        self.b_open.setToolTip("Open the draft in your writing app (Ctrl+E)")
        for w in (b_browse, b_new, self.b_open):
            w.setAutoDefault(False)
        lay.addWidget(self.line, 1)
        lay.addWidget(self.words)
        lay.addWidget(b_browse)
        lay.addWidget(b_new)
        lay.addWidget(self.b_open)
        self.line.textEdited.connect(self.changed)
        b_browse.clicked.connect(self.browse)
        b_new.clicked.connect(self.create)
        self.b_open.clicked.connect(self.open)

    def value(self) -> str:
        return self.line.text().strip()

    def set_value(self, v):
        self.line.setText(str(v) if v else "")

    def set_words(self, n, exists=True):
        if not self.value():
            self.words.setText("")
        elif not exists:
            self.words.setText("⚠ missing")
        else:
            self.words.setText(f"{n:,} words" if n is not None else "? words")
        self.b_open.setEnabled(bool(self.value()) and exists)


class WikiHighlighter(QSyntaxHighlighter):
    def __init__(self, doc, resolves):
        super().__init__(doc)
        self.resolves = resolves
        self.ok = QTextCharFormat()
        self.ok.setFontUnderline(True)
        self.missing = QTextCharFormat()
        self.missing.setFontUnderline(True)
        self.missing.setUnderlineStyle(QTextCharFormat.DashUnderline)
        self.update_colors()
        self.heading = QTextCharFormat()
        self.heading.setFontWeight(QFont.Bold)

    def update_colors(self):
        from .theme import accent
        self.ok.setForeground(QColor(accent("link")))
        self.missing.setForeground(QColor(accent("missing")))
        self.rehighlight()

    def highlightBlock(self, text):
        if text.startswith("#"):
            self.setFormat(0, len(text), self.heading)
        for m in LINK_RE.finditer(text):
            fmt = self.ok if self.resolves(m.group(1)) else self.missing
            self.setFormat(m.start(), m.end() - m.start(), fmt)


class WikiTextEdit(QPlainTextEdit):
    """Notes editor: type [[ for name autocomplete, Ctrl+click a link to follow it."""
    linkActivated = Signal(str)

    def __init__(self, resolves, parent=None):
        super().__init__(parent)
        self.setTabChangesFocus(False)
        self.completer = make_completer(self)
        self.completer.setWidget(self)
        self.completer.activated.connect(self._insert_completion)
        self.highlighter = WikiHighlighter(self.document(), resolves)
        self.setMouseTracking(True)
        self.setPlaceholderText("Notes… type [[ to link a character, place, scene or anything else.")

    def set_options(self, names):
        self.completer.model().setStringList(list(names))

    def _link_context(self):
        c = self.textCursor()
        before = c.block().text()[:c.positionInBlock()]
        i = before.rfind("[[")
        if i < 0:
            return None
        seg = before[i + 2:]
        if any(ch in seg for ch in "[]|#"):
            return None
        return seg

    def keyPressEvent(self, e):
        popup = self.completer.popup()
        if popup.isVisible() and e.key() in (Qt.Key_Enter, Qt.Key_Return, Qt.Key_Escape,
                                             Qt.Key_Tab, Qt.Key_Backtab):
            e.ignore()
            return
        super().keyPressEvent(e)
        if e.modifiers() & Qt.ControlModifier and not e.text():
            return
        seg = self._link_context()
        if seg is None:
            popup.hide()
            return
        self.completer.setCompletionPrefix(seg)
        if self.completer.completionCount() == 0:
            popup.hide()
            return
        popup.setCurrentIndex(self.completer.completionModel().index(0, 0))
        r = self.cursorRect()
        r.setWidth(max(220, popup.sizeHintForColumn(0) + popup.verticalScrollBar().sizeHint().width() + 24))
        self.completer.complete(r)

    def _insert_completion(self, text):
        seg = self._link_context()
        if seg is None:
            return
        c = self.textCursor()
        c.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor, len(seg))
        c.insertText(text)
        rest = c.block().text()[c.positionInBlock():]
        if rest.startswith("]]"):
            c.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, 2)
        else:
            c.insertText("]]")
        self.setTextCursor(c)

    def _link_at(self, pos):
        c = self.cursorForPosition(pos)
        text, at = c.block().text(), c.positionInBlock()
        for m in LINK_RE.finditer(text):
            if m.start() <= at <= m.end():
                return m.group(1)
        return None

    def mouseMoveEvent(self, e):
        over = bool(e.modifiers() & Qt.ControlModifier) and self._link_at(e.position().toPoint())
        self.viewport().setCursor(Qt.PointingHandCursor if over else Qt.IBeamCursor)
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and e.modifiers() & Qt.ControlModifier:
            target = self._link_at(e.position().toPoint())
            if target:
                self.linkActivated.emit(target)
                return
        super().mouseReleaseEvent(e)


# ============================================================================ images

IMAGE_FILTER = "Images (*.png *.jpg *.jpeg *.webp *.gif *.bmp);;All files (*)"
_thumb_cache: dict = {}


def _load_image(path: Path):
    from PySide6.QtGui import QImageReader
    r = QImageReader(str(path))
    r.setAutoTransform(True)
    img = r.read()
    return None if img.isNull() else img


def thumbnail(path, w: int, h: int, crop: bool = False):
    """Scaled pixmap of an image file (cached). crop=True fills w×h, keeping the top
    of the picture, where faces usually are."""
    if path is None:
        return None
    path = Path(path)
    try:
        st = path.stat()
    except OSError:
        return None
    key = (str(path), st.st_mtime, st.st_size, w, h, crop)
    if key in _thumb_cache:
        return _thumb_cache[key]
    img = _load_image(path)
    if img is None:
        _thumb_cache[key] = None
        return None
    if crop:
        img = img.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        x = (img.width() - w) // 2
        y = int((img.height() - h) * 0.15)
        img = img.copy(x, y, w, h)
    else:
        img = img.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    pm = QPixmap.fromImage(img)
    if len(_thumb_cache) > 400:
        _thumb_cache.clear()
    _thumb_cache[key] = pm
    return pm


def image_size(path):
    from PySide6.QtGui import QImageReader
    r = QImageReader(str(path))
    r.setAutoTransform(True)
    return r.size()


def avatar(name: str, path, size: int) -> QPixmap:
    """Rounded portrait thumbnail, or a colored circle with initials when there's no image."""
    from PySide6.QtGui import QPainterPath
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    clip = QPainterPath()
    clip.addRoundedRect(0, 0, size, size, size * 0.22, size * 0.22)
    thumb = thumbnail(path, size, size, crop=True) if path else None
    if thumb is not None:
        p.setClipPath(clip)
        p.drawPixmap(0, 0, thumb)
    else:
        palette = ["#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f", "#b07aa1", "#9c755f", "#d37295"]
        col = QColor(palette[sum(map(ord, name)) % len(palette)])
        p.fillPath(clip, col)
        initials = "".join(w[0] for w in name.split()[:2]).upper() or "?"
        f = QFont()
        f.setBold(True)
        f.setPixelSize(int(size * 0.38))
        p.setFont(f)
        p.setPen(QColor("white"))
        p.drawText(pm.rect(), Qt.AlignCenter, initials)
    p.end()
    return pm


def _image_files(mime) -> list[Path]:
    from ..model import IMAGE_EXTS
    out = []
    if mime.hasUrls():
        for u in mime.urls():
            if u.isLocalFile():
                p = Path(u.toLocalFile())
                if p.suffix.lower() in IMAGE_EXTS and p.is_file():
                    out.append(p)
    return out


class PortraitPanel(QWidget):
    """A character's portrait plus a strip of alternate images (e.g. other generations).
    Values are Obsidian-style [[file.png]] links to copies kept in the project's images/."""
    changed = Signal()
    openFile = Signal(object)

    W, H = 200, 260

    def __init__(self, resolve, importer, parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QAbstractItemView, QListView, QListWidget, QSizePolicy, QVBoxLayout
        self.resolve, self.importer = resolve, importer
        self.portrait = ""
        self.images: list[str] = []
        self.setAcceptDrops(True)
        self.setFixedWidth(self.W + 8)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 0, 4, 0)
        lay.setSpacing(4)
        self.pic = QLabel()
        self.pic.setFixedSize(self.W, self.H)
        self.pic.setAlignment(Qt.AlignCenter)
        self.pic.setWordWrap(True)
        self.pic.setContextMenuPolicy(Qt.CustomContextMenu)
        self.pic.customContextMenuRequested.connect(self._pic_menu)
        self.pic.mouseDoubleClickEvent = lambda e: self._open(self.portrait)
        lay.addWidget(self.pic)
        row = QHBoxLayout()
        self.b_choose = QPushButton("Choose…")
        self.b_choose.setToolTip("Pick one or more images. The first becomes the portrait (if there "
                                 "isn't one yet); the rest go in the gallery.")
        self.b_remove = QPushButton("Remove")
        self.b_remove.setToolTip("Stop using this portrait (the image file stays in images/).")
        for b in (self.b_choose, self.b_remove):
            b.setAutoDefault(False)
        self.b_choose.clicked.connect(self.choose)
        self.b_remove.clicked.connect(self.remove_portrait)
        row.addWidget(self.b_choose)
        row.addWidget(self.b_remove)
        lay.addLayout(row)
        self.gal_label = QLabel()
        self.gal_label.setStyleSheet("color: palette(mid);")
        lay.addWidget(self.gal_label)
        self.gallery = QListWidget()
        self.gallery.setViewMode(QListView.IconMode)
        self.gallery.setFlow(QListView.LeftToRight)
        self.gallery.setWrapping(False)
        self.gallery.setMovement(QListView.Static)
        self.gallery.setIconSize(QSize(56, 72))
        self.gallery.setFixedHeight(92)
        self.gallery.setSpacing(2)
        self.gallery.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.gallery.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.gallery.setContextMenuPolicy(Qt.CustomContextMenu)
        self.gallery.customContextMenuRequested.connect(self._gallery_menu)
        self.gallery.itemDoubleClicked.connect(lambda it: self.use_as_portrait(it.data(Qt.UserRole)))
        self.gallery.setToolTip("Double-click to use as the portrait. Right-click for more.")
        self.gallery.setAcceptDrops(False)
        lay.addWidget(self.gallery)
        lay.addStretch(1)

    # ------------------------------------------------------------ values
    def set_values(self, portrait, images):
        self.portrait = str(portrait or "")
        self.images = [str(x) for x in (images or []) if x] if isinstance(images, list) else \
            ([str(images)] if images else [])
        self._render()

    def portrait_value(self) -> str:
        return self.portrait

    def images_value(self) -> list:
        return list(self.images)

    # ------------------------------------------------------------ display
    def _render(self):
        path = self.resolve(self.portrait) if self.portrait else None
        pm = thumbnail(path, self.W, self.H) if path else None
        if pm is not None:
            self.pic.setPixmap(pm)
            self.pic.setStyleSheet("")
            self.pic.setToolTip(f"{path.name}\nDouble-click to open. Drop another image here to replace it.")
        else:
            self.pic.setPixmap(QPixmap())
            if self.portrait:
                self.pic.setText(f"⚠ Can't find\n{strip_link(self.portrait)}")
            else:
                self.pic.setText("Drop a portrait here\nor click Choose…")
            self.pic.setStyleSheet("border: 2px dashed palette(mid); border-radius: 8px; color: palette(mid);")
            self.pic.setToolTip("")
        self.b_remove.setEnabled(bool(self.portrait))
        self.gallery.clear()
        from PySide6.QtWidgets import QListWidgetItem
        for link in self.images:
            p = self.resolve(link)
            pm = thumbnail(p, 56, 72, crop=True) if p else None
            it = QListWidgetItem(QIcon(pm) if pm else QIcon(), "" if pm else "?")
            it.setData(Qt.UserRole, link)
            it.setToolTip(strip_link(link) + ("" if p else "  (missing)"))
            self.gallery.addItem(it)
        n = len(self.images)
        self.gal_label.setText(f"Gallery ({n}) · drop images here" if n else "Gallery · drop images here")

    # ------------------------------------------------------------ actions
    def _import(self, path: Path) -> str | None:
        try:
            return self.importer(path)
        except OSError:
            return None

    def set_portrait_file(self, path: Path):
        link = self._import(path)
        if not link or link == self.portrait:
            return
        if self.portrait and self.portrait not in self.images:
            self.images.insert(0, self.portrait)
        self.images = [x for x in self.images if x != link]
        self.portrait = link
        self._render()
        self.changed.emit()

    def add_gallery_file(self, path: Path):
        link = self._import(path)
        if link and link != self.portrait and link not in self.images:
            self.images.append(link)
            self._render()
            self.changed.emit()

    def use_as_portrait(self, link):
        if not link or link == self.portrait:
            return
        self.images = [x for x in self.images if x != link]
        if self.portrait:
            self.images.insert(0, self.portrait)
        self.portrait = link
        self._render()
        self.changed.emit()

    def remove_portrait(self):
        if self.portrait:
            self.portrait = ""
            self._render()
            self.changed.emit()

    def move_portrait_to_gallery(self):
        if self.portrait:
            self.images.insert(0, self.portrait)
            self.portrait = ""
            self._render()
            self.changed.emit()

    def remove_from_gallery(self, link):
        self.images = [x for x in self.images if x != link]
        self._render()
        self.changed.emit()

    def choose(self):
        from PySide6.QtWidgets import QFileDialog
        files, _ = QFileDialog.getOpenFileNames(self, "Choose images", "", IMAGE_FILTER)
        self._take([Path(f) for f in files], portrait_first=not self.portrait)

    def _take(self, files, portrait_first):
        for i, f in enumerate(files):
            if i == 0 and portrait_first:
                self.set_portrait_file(f)
            else:
                self.add_gallery_file(f)

    def _open(self, link):
        p = self.resolve(link) if link else None
        if p:
            self.openFile.emit(p)

    def _pic_menu(self, pos):
        from PySide6.QtWidgets import QMenu
        m = QMenu(self)
        m.addAction("Choose…", self.choose)
        if self.portrait:
            m.addAction("Open image", lambda: self._open(self.portrait))
            m.addAction("Move to gallery", self.move_portrait_to_gallery)
            m.addAction("Remove portrait", self.remove_portrait)
        m.exec(self.pic.mapToGlobal(pos))

    def _gallery_menu(self, pos):
        from PySide6.QtWidgets import QMenu
        it = self.gallery.itemAt(pos)
        if not it:
            return
        link = it.data(Qt.UserRole)
        m = QMenu(self)
        m.addAction("Use as portrait", lambda: self.use_as_portrait(link))
        m.addAction("Open image", lambda: self._open(link))
        m.addAction("Remove from gallery", lambda: self.remove_from_gallery(link))
        m.exec(self.gallery.viewport().mapToGlobal(pos))

    # ------------------------------------------------------------ drag & drop
    def dragEnterEvent(self, e):
        if self.isEnabled() and _image_files(e.mimeData()):
            e.acceptProposedAction()

    def dragMoveEvent(self, e):
        if _image_files(e.mimeData()):
            e.acceptProposedAction()

    def dropEvent(self, e):
        files = _image_files(e.mimeData())
        if not files:
            return
        on_pic = self.pic.geometry().contains(e.position().toPoint())
        e.acceptProposedAction()
        self._take(files, portrait_first=on_pic or not self.portrait)
