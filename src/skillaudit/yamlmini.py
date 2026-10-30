# -*- coding: utf-8 -*-
"""Minimal YAML subset parser written from scratch for SkillAudit.

Why reinvent this wheel?
------------------------
SkillAudit promises **zero third-party dependencies** so it can run inside
air-gapped CI runners, agent sandboxes and tiny containers. Pulling in PyYAML
for a front-matter block that realistically contains nothing but scalars,
block mappings and simple sequences would violate that promise.

The parser deliberately supports only the YAML subset that skill manifests
actually use, and fails loudly (``YamlMiniError``) instead of guessing when it
meets something exotic:

* ``key: value`` block mappings with indentation-based nesting
* ``- item`` block sequences (including nested mappings inside a sequence)
* inline scalars, quoted scalars (single / double) and folded block scalars
  (``>-``, ``>-``, ``|``, ``|-``, ``|+``)
* comments introduced by ``#`` outside of quoted scalars
* trailing trailing ``key:`` (empty value → ``None``)

Unsupported on purpose: anchors/aliases, flow mappings ``{a: 1}``, tags,
multiple documents, and the twelve ways of writing ``null``. These never show
up in a well-formed ``SKILL.md`` front matter, and silently mis-parsing them
would be worse than an honest error.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


class YamlMiniError(ValueError):
    """Raised when the input uses YAML features outside the supported subset."""


_FRONT_MATTER_RE = re.compile(
    r"\A\s*---\s*\r?\n(?P<body>.*?)(?:\r?\n)?---\s*(?:\r?\n|\Z)",
    re.DOTALL,
)

_KEY_RE = re.compile(r"^(?P<key>[A-Za-z0-9_.\-\/ ]+?)\s*:(?:\s+(?P<val>.*))?$")
_SEQ_RE = re.compile(r"^-\s*(?P<val>.*)$")


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

def extract_front_matter(text):
    """Return ``(mapping_or_None, body_after_front_matter, line_offset)``.

    ``line_offset`` is the number of lines consumed by the delimiters, useful
    for mapping errors back to real file line numbers.
    """
    if text is None:
        return None, "", 0
    match = _FRONT_MATTER_RE.match(text)
    if not match:
        return None, text, 0

    body = match.group("body")
    if not body.strip():
        return {}, text[match.end():], 0

    lines = body.splitlines()
    consumed = len(lines) + 2  # both '---' fences
    parsed = loads("\n".join(lines))
    if parsed is None:
        parsed = {}
    if not isinstance(parsed, dict):
        raise YamlMiniError("front matter must decode to a mapping")
    return parsed, text[match.end():], consumed


def loads(text):
    """Parse a YAML subset document and return the decoded Python object."""
    if text is None:
        return None
    raw_lines = text.splitlines()
    lines = []  # (indent, content, line_no)
    for idx, raw in enumerate(raw_lines, start=1):
        stripped = raw.rstrip()
        if stripped and not stripped.strip():
            # Whitespace-only lines still count as content inside block scalars.
            indent = len(stripped) - len(stripped.lstrip(" "))
            lines.append((indent, "", idx))
            continue
        if not stripped.strip():
            lines.append((0, "", idx))  # blank lines are meaningful inside blocks
            continue
        if stripped.lstrip().startswith("#"):
            continue
        indent = len(stripped) - len(stripped.lstrip(" "))
        lines.append((indent, stripped.strip(), idx))

    if not lines:
        return None
    value, _ = _parse_block(lines, 0, lines[0][0])
    return value


# --------------------------------------------------------------------------
# Internals
# --------------------------------------------------------------------------

def _strip_comment(content):
    """Remove a trailing ``#`` comment, honouring quoted scalars.

    A ``#`` inside a quoted scalar is data, not a comment — jumping to the
    first hash unconditionally would silently truncate values such as
    ``password: "abcd#1234"``.
    """
    quote = None
    prev_space = True
    for index, ch in enumerate(content):
        if quote:
            if ch == quote:
                quote = None
            continue
        if ch in ("'", '"'):
            quote = ch
            continue
        if prev_space and ch == "#":
            return content[:index].rstrip()
        prev_space = ch in (" ", "\t")
    return content.rstrip()


def _scalar(token):
    """Convert a scalar token into ``str`` / ``int`` / ``float`` / ``bool`` / ``None``."""
    token = token.strip()
    if not token:
        return None

    if len(token) >= 2 and token[0] == token[-1] and token[0] in ("'", '"'):
        inner = token[1:-1]
        return inner.replace("''", "'") if token[0] == "'" else _unescape(inner)

    lowered = token.lower()
    if lowered in ("true", "yes", "on"):
        return True
    if lowered in ("false", "no", "off"):
        return False
    if lowered in ("null", "~", "none"):
        return None

    try:
        return int(token)
    except ValueError:
        pass
    try:
        return float(token)
    except ValueError:
        pass
    return token


def _unescape(value):
    result = []
    i = 0
    while i < len(value):
        ch = value[i]
        if ch == "\\" and i + 1 < len(value):
            nxt = value[i + 1]
            mapping = {"n": "\n", "t": "\t", "r": "\r", "0": "\0",
                       "\\": "\\", '"': '"', "/": "/"}
            result.append(mapping.get(nxt, nxt))
            i += 2
            continue
        result.append(ch)
        i += 1
    return "".join(result)


def _collect_block_scalar(lines, index, indent, marker):
    """Handle ``|`` (literal) and ``>`` (folded) block scalars."""
    chomp = "clip"
    if marker.endswith("-"):
        chomp = "strip"
        marker = marker[:-1]
    elif marker.endswith("+"):
        chomp = "keep"
        marker = marker[:-1]

    chunks = []
    i = index + 1
    while i < len(lines):
        cur_indent, content, _ = lines[i]
        if content and cur_indent <= indent:
            break
        chunks.append(content)
        i += 1

    if marker.startswith(">"):
        text = _fold(chunks)
    else:
        text = "\n".join(chunks)

    if chomp == "strip":
        return text.rstrip("\n"), i
    if chomp == "keep":
        return text + "\n", i
    return text.rstrip("\n") + "\n", i


def _fold(chunks):
    out = []
    blank_run = False
    for line in chunks:
        if not line.strip():
            if not blank_run and out:
                out.append("\n")
            blank_run = True
            continue
        blank_run = False
        if out and out[-1] != "\n":
            out.append(" ")
        out.append(line)
    return "".join(out)


def _parse_block(lines, start, indent):
    """Parse either a mapping or a sequence starting at ``start``."""
    i = start
    if i >= len(lines):
        return None, i

    first_indent, first_content, _ = lines[i]
    if _SEQ_RE.match(first_content) or first_content == "-":
        return _parse_sequence(lines, i, first_indent if first_indent > indent else indent)
    return _parse_mapping(lines, i, indent)


def _parse_sequence(lines, start, indent):
    seq = []
    i = start
    while i < len(lines):
        cur_indent, content, lineno = lines[i]
        if content == "":
            i += 1
            continue
        if cur_indent < indent:
            break
        match = _SEQ_RE.match(content)
        if not match:
            if content == "-":
                value, i = _parse_child(lines, i + 1, cur_indent)
                seq.append(value)
                continue
            break
        value_token = match.group("val").strip()
        i += 1
        if ":" in value_token and _KEY_RE.match(value_token):
            # inline start of a nested mapping: "- key: value"
            sub_lines = [(cur_indent + 2, value_token, lineno)]
            while i < len(lines) and lines[i][0] > cur_indent:
                sub_lines.append(lines[i])
                i += 1
            mapping, _ = _parse_mapping(sub_lines, 0, cur_indent + 2)
            seq.append(mapping)
            continue
        scalar, next_index = _maybe_block_scalar(value_token, lines, i, cur_indent)
        if next_index is not None:
            i = next_index
        seq.append(scalar)
    return seq, i


def _maybe_block_scalar(token, lines, i, indent):
    """Return ``(value, next_index)`` for a possible block scalar.

    ``next_index`` is absolute. When the token is an ordinary inline scalar it
    comes back as ``None`` so the caller keeps its current cursor position.
    Returning an absolute index (rather than a delta) avoids the classic
    double-advance bug where the entries following a folded scalar get skipped.
    """
    lowered = token.strip()
    if lowered.startswith("|") or lowered.startswith(">"):
        return _collect_block_scalar(lines, i - 1, indent, lowered)
    return _scalar(token), None


def _parse_child(lines, i, parent_indent):
    """Parse a nested block (mapping or sequence) below ``parent_indent``."""
    if i >= len(lines):
        return None, i
    cur_indent = lines[i][0]
    if cur_indent <= parent_indent:
        return None, i
    return _parse_block(lines, i, cur_indent)


def _parse_mapping(lines, start, indent):
    mapping = {}
    i = start
    while i < len(lines):
        cur_indent, content, lineno = lines[i]
        if content == "":
            # Blank lines are structural noise at mapping level; inside block
            # scalars they are data, and were already consumed there.
            i += 1
            continue
        if cur_indent < indent:
            break
        if cur_indent > indent:
            # Stray deeper line inside a mapping: treat as malformed and stop.
            raise YamlMiniError(
                "unexpected indentation at line %d: %r" % (lineno, content))

        match = _KEY_RE.match(content)
        if not match:
            seq_match = _SEQ_RE.match(content)
            if seq_match:
                break
            raise YamlMiniError("cannot parse line %d: %r" % (lineno, content))

        key = match.group("key").strip()
        raw_value = match.group("val")
        i += 1

        if raw_value is None or raw_value == "":
            child, i = _parse_child(lines, i, indent)
            mapping[key] = child
            continue

        lowered = raw_value.strip()
        if lowered.startswith("|") or lowered.startswith(">"):
            scalar, next_index = _collect_block_scalar(lines, i - 1, indent, lowered)
            i = next_index
            mapping[key] = scalar
            continue

        mapping[key] = _scalar(_strip_comment(raw_value))
    return mapping, i
