"""Reading and writing Markdown files with YAML frontmatter (Obsidian style)."""
from __future__ import annotations

import re

import yaml

_FM = re.compile(r"\A---[ \t]*\r?\n(.*?)^---[ \t]*\r?$\n?", re.S | re.M)


class _Dumper(yaml.SafeDumper):
    """Block-style lists indented the way Obsidian writes them."""

    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


def _str_rep(dumper, data):
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


_Dumper.add_representer(str, _str_rep)


def parse(text: str):
    """Return (meta, body, ok). ok is False when the frontmatter is not valid YAML;
    in that case meta is empty and body is the whole text, so nothing is lost."""
    text = text.lstrip("﻿")
    m = _FM.match(text)
    if not m:
        return {}, text, True
    try:
        data = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return {}, text, False
    if data is None:
        data = {}
    if not isinstance(data, dict):
        return {}, text, False
    return data, text[m.end():], True


def dump(meta: dict, body: str) -> str:
    if not meta:
        return body
    fm = yaml.dump(meta, Dumper=_Dumper, sort_keys=False, allow_unicode=True,
                   default_flow_style=False, width=4096)
    return "---\n" + fm + "---\n" + body


def dump_value(value) -> str:
    """One-line text form of a property value, for display in a table."""
    if isinstance(value, str):
        return value
    return yaml.dump(value, Dumper=_Dumper, default_flow_style=True, allow_unicode=True,
                     width=4096).strip().removesuffix("...").strip()


def load_value(text: str):
    """Inverse of dump_value, forgiving: falls back to the plain string."""
    t = text.strip()
    if not t:
        return ""
    if t.startswith("[["):
        return t
    try:
        v = yaml.safe_load(t)
    except yaml.YAMLError:
        return t
    return t if v is None else v
