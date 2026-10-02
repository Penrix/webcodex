from __future__ import annotations

import json
from typing import Any

MARKDOWN_PUNCTUATION = set("!#()*+-.<>[]_{}|~")
VALID_JSON_ESCAPES = set('"\\/bfnrtu')


def undo_turndown_json_escapes(text: str) -> str:
    out: list[str] = []
    in_string = False
    index = 0
    while index < len(text):
        ch = text[index]
        if ch == '"':
            in_string = not in_string
            out.append(ch)
            index += 1
            continue
        if ch != "\\" or index + 1 >= len(text):
            out.append(ch)
            index += 1
            continue
        nxt = text[index + 1]
        if in_string and nxt in VALID_JSON_ESCAPES:
            out.extend((ch, nxt))
            index += 2
            continue
        if nxt in MARKDOWN_PUNCTUATION:
            out.append(nxt)
            index += 2
            continue
        out.extend((ch, nxt))
        index += 2
    return "".join(out)


def parse_json_object_from_markdown(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except ValueError as first_error:
        normalized = undo_turndown_json_escapes(text)
        if normalized == text:
            raise
        try:
            value = json.loads(normalized)
        except ValueError:
            raise first_error
    if not isinstance(value, dict):
        raise ValueError("JSON value was not an object")
    return value
