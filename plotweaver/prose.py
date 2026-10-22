"""Word counts for linked draft files (txt, md, odt, docx, rtf)."""
from __future__ import annotations

import html
import re
import zipfile
from pathlib import Path

from . import mdio

WORD_RE = re.compile(r"\w[\w'’\-]*", re.UNICODE)
PROSE_FILTER = "Draft files (*.txt *.md *.markdown *.odt *.docx *.rtf *.fwr *.fountain);;All files (*)"


def count_words(text: str) -> int:
    return len(WORD_RE.findall(text))


def _xml_text(xml: str, para_end: str, spaces: list[str]) -> str:
    for pat in spaces:
        xml = re.sub(pat, " ", xml)
    xml = re.sub(para_end, "\n", xml)
    xml = re.sub(r"<[^>]+>", "", xml)
    return html.unescape(xml)


_RTF_PAT = re.compile(
    r"\\([a-z]{1,32})(-?\d{1,10})?[ ]?|\\'([0-9a-f]{2})|\\([^a-z])|([{}])|[\r\n]+|(.)", re.I | re.S)
_RTF_DEST = {
    "aftncn", "aftnsep", "aftnsepc", "annotation", "atnauthor", "atndate", "atnicn", "atnid",
    "atnparent", "atnref", "atntime", "atrfend", "atrfstart", "author", "background", "bkmkend",
    "bkmkstart", "buptim", "category", "colortbl", "comment", "company", "creatim", "datafield",
    "datastore", "defchp", "defpap", "do", "doccomm", "docvar", "dptxbxtext", "ebcend", "ebcstart",
    "falt", "fchars", "ffdeftext", "ffentrymcr", "ffexitmcr", "ffformat", "ffhelptext", "ffl",
    "ffname", "ffstattext", "field", "file", "filetbl", "fldinst", "fldtype", "fname",
    "fontemb", "fontfile", "fonttbl", "footer", "footerf", "footerl", "footerr", "footnote",
    "formfield", "ftncn", "ftnsep", "ftnsepc", "g", "generator", "gridtbl", "header", "headerf",
    "headerl", "headerr", "hl", "hlfr", "hlinkbase", "hlloc", "hlsrc", "hsv", "info", "keywords",
    "latentstyles", "lchars", "levelnumbers", "leveltext", "lfolevel", "linkval", "list",
    "listlevel", "listname", "listoverride", "listoverridetable", "listpicture", "liststylename",
    "listtable", "listtext", "lsdlockedexcept", "macc", "maccPr", "mailmerge", "manager", "mmath",
    "mmathPr", "nonshppict", "objdata", "objtime", "operator", "pict", "pn", "pnseclvl",
    "pntext", "pntxta", "pntxtb", "printim", "private", "propname", "protend", "protstart",
    "protusertbl", "pxe", "result", "revtbl", "revtim", "rsidtbl", "rxe", "shp", "shpgrp",
    "shpinst", "shppict", "shprslt", "shptxt", "sn", "sp", "staticval", "stylesheet", "subject",
    "sv", "svb", "tc", "template", "themedata", "title", "txe", "ud", "upr", "userprops",
    "wgrffmtfilter", "windowcaption", "writereservation", "writereservhash", "xe", "xform",
    "xmlattrname", "xmlattrvalue", "xmlclose", "xmlname", "xmlnstbl", "xmlopen",
}
_RTF_SPECIAL = {
    "par": "\n", "sect": "\n\n", "page": "\n\n", "line": "\n", "tab": " ", "emdash": "—",
    "endash": "–", "emspace": " ", "enspace": " ", "qmspace": " ", "bullet": "•",
    "lquote": "‘", "rquote": "’", "ldblquote": "“", "rdblquote": "”",
}


def rtf_to_text(text: str) -> str:
    stack, out = [], []
    ignorable, ucskip, curskip = False, 1, 0
    for m in _RTF_PAT.finditer(text):
        word, arg, hexc, char, brace, tchar = m.groups()
        if brace:
            curskip = 0
            if brace == "{":
                stack.append((ucskip, ignorable))
            elif stack:
                ucskip, ignorable = stack.pop()
        elif char:
            curskip = 0
            if char == "~":
                if not ignorable:
                    out.append("\xa0")
            elif char in "{}\\":
                if not ignorable:
                    out.append(char)
            elif char == "*":
                ignorable = True
        elif word:
            curskip = 0
            if word in _RTF_DEST:
                ignorable = True
            elif ignorable:
                pass
            elif word in _RTF_SPECIAL:
                out.append(_RTF_SPECIAL[word])
            elif word == "uc" and arg:
                ucskip = int(arg)
            elif word == "u" and arg:
                c = int(arg)
                if c < 0:
                    c += 0x10000
                out.append(chr(c))
                curskip = ucskip
        elif hexc:
            if curskip > 0:
                curskip -= 1
            elif not ignorable:
                out.append(bytes([int(hexc, 16)]).decode("cp1252", "replace"))
        elif tchar:
            if curskip > 0:
                curskip -= 1
            elif not ignorable:
                out.append(tchar)
    return "".join(out)


def read_text(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".odt":
        with zipfile.ZipFile(path) as z:
            xml = z.read("content.xml").decode("utf-8", "replace")
        return _xml_text(xml, r"</text:(?:p|h)>",
                         [r"<text:s(?:\s[^>]*)?/>", r"<text:tab\s*/>", r"<text:line-break\s*/>"])
    if ext == ".docx":
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml").decode("utf-8", "replace")
        return _xml_text(xml, r"</w:p>", [r"<w:tab\s*/>", r"<w:br[^>]*/>"])
    raw = path.read_bytes()
    if ext in (".rtf", ".fwr") or raw.startswith(b"{\\rtf"):
        return rtf_to_text(raw.decode("latin-1"))
    text = raw.decode("utf-8", "replace")
    if ext in (".md", ".markdown"):
        _, text, _ = mdio.parse(text)
    return text


def word_count(path: Path) -> int | None:
    try:
        return count_words(read_text(path))
    except (OSError, KeyError, zipfile.BadZipFile, ValueError):
        return None
