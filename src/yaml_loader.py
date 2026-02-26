from __future__ import annotations

from typing import Any


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return ""
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        parts = [part.strip() for part in inner.split(",")]
        return [_parse_scalar(part) for part in parts]
    if value.startswith(('"', "'")) and value.endswith(('"', "'")):
        return value[1:-1]
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def load_yaml(text: str) -> Any:
    lines = [
        line.rstrip("\n")
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    def parse_block(start: int, indent: int) -> tuple[Any, int]:
        if start >= len(lines):
            return {}, start
        is_list = lines[start].startswith(" " * indent + "- ")
        if is_list:
            items = []
            index = start
            while index < len(lines):
                line = lines[index]
                if not line.startswith(" " * indent + "- "):
                    break
                content = line[indent + 2 :].strip()
                item: Any
                inline_dict = {}
                if ":" in content:
                    key, raw_val = content.split(":", 1)
                    inline_dict[key.strip()] = _parse_scalar(raw_val)
                    item = inline_dict
                else:
                    item = _parse_scalar(content)
                index += 1
                if index < len(lines):
                    next_line = lines[index]
                    next_indent = len(next_line) - len(next_line.lstrip(" "))
                    if next_indent > indent:
                        nested, index = parse_block(index, next_indent)
                        if isinstance(item, dict) and isinstance(nested, dict):
                            item.update(nested)
                        else:
                            item = nested
                items.append(item)
            return items, index

        mapping: dict[str, Any] = {}
        index = start
        while index < len(lines):
            line = lines[index]
            current_indent = len(line) - len(line.lstrip(" "))
            if current_indent < indent:
                break
            if line.startswith(" " * indent + "- "):
                break
            key, raw_val = line[indent:].split(":", 1)
            key = key.strip()
            raw_val = raw_val.strip()
            index += 1
            if raw_val == "":
                nested, index = parse_block(index, indent + 2)
                mapping[key] = nested
            else:
                mapping[key] = _parse_scalar(raw_val)
        return mapping, index

    parsed, _ = parse_block(0, 0)
    return parsed
