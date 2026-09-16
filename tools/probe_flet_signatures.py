#!/usr/bin/env python3
"""Flet 构造签名与枚举成员探针（第二轮）。

第一轮只确认了"有没有"，这一轮确认"怎么传参"以及枚举里到底有哪些成员名，
避免写出关键词拼错的代码。
"""

from __future__ import annotations

import inspect

import flet as ft

CLASSES = (
    "Page", "Container", "Stack", "Column", "Row", "Text", "TextField",
    "Checkbox", "Dropdown", "DropdownOption", "Button", "FilledButton",
    "OutlinedButton", "TextButton", "IconButton", "NavigationBar",
    "NavigationBarDestination", "AlertDialog", "GestureDetector", "SafeArea",
    "SnackBar", "Card", "Icon", "Divider", "TextField",
)

print("=" * 72)
print("构造参数（只列出我们可能用到的字段）")
print("=" * 72)
INTERESTING = {
    "left", "top", "right", "bottom", "width", "height", "bgcolor", "color",
    "content", "controls", "text", "value", "label", "hint_text", "options",
    "icon", "tooltip", "on_click", "on_change", "expand", "spacing",
    "run_spacing", "wrap", "disabled", "selected_index", "destinations",
    "title", "actions", "modal", "size", "weight", "text_align", "no_wrap",
    "overflow", "alignment", "padding", "margin", "border_radius", "border",
    "scroll", "keyboard_type", "multiline", "max_lines", "min_lines", "rows",
    "vertical_alignment", "horizontal_alignment", "ink", "selected",
    "control", "controls_padding", "label_visibility", "data", "visible",
    "auto_scroll", "text_size", "label_text_style", "bgcolor",
}

# 这些类在 Flet 1.0 里是 dataclass，signature 直接可用
for name in CLASSES:
    cls = getattr(ft, name, None)
    if cls is None:
        print(f"\n{name}: 缺失")
        continue
    try:
        params = list(inspect.signature(cls).parameters)
    except (TypeError, ValueError) as exc:
        print(f"\n{name}: 无法取签名（{exc}）")
        continue
    show = [p for p in params if p in INTERESTING]
    print(f"\n{name}:")
    print(f"  全部参数({len(params)}): {', '.join(params)}")
    print(f"  我们要用的: {', '.join(show) if show else '（无匹配）'}")

print()
print("=" * 72)
print("枚举成员")
print("=" * 72)
for enum_name, wanted in (
    ("ScrollMode", ("AUTO", "ALWAYS", "HIDDEN")),
    ("KeyboardType", ("TEXT", "NUMBER", "MULTILINE", "DATETIME")),
    ("MainAxisAlignment", ("START", "CENTER", "SPACE_BETWEEN", "END")),
    ("CrossAxisAlignment", ("START", "CENTER", "END", "STRETCH")),
    ("TextAlign", ("LEFT", "CENTER", "RIGHT", "JUSTIFY")),
    ("FontWeight", ("NORMAL", "MEDIUM", "BOLD", "W_500", "W_600")),
    ("Icons", ("ADD", "CHEVRON_LEFT", "CHEVRON_RIGHT", "TODAY", "SETTINGS",
               "CALENDAR_MONTH", "EDIT", "DELETE", "CLOSE", "CHECK", "SAVE",
               "ARROW_BACK", "ARROW_FORWARD", "LIST", "GRID_VIEW", "EVENT",
               "LOCATION_ON", "PERSON", "SCHOOL", "TUNE", "REFRESH")),
    ("Colors", ("WHITE", "BLACK", "GREY_100", "GREY_200", "GREY_300",
                "GREY_500", "GREY_700", "GREY_800", "BLUE", "RED",
                "TRANSPARENT", "BLUE_GREY_50", "SURFACE", "OUTLINE_VARIANT")),
    ("TextOverflow", ("ELLIPSIS", "CLIP", "FADE")),
):
    enum_cls = getattr(ft, enum_name, None)
    if enum_cls is None:
        print(f"  {enum_name}: 缺失")
        continue
    present = [w for w in wanted if hasattr(enum_cls, w)]
    absent = [w for w in wanted if not hasattr(enum_cls, w)]
    print(f"  {enum_name}:")
    print(f"    可用: {', '.join(present) if present else '无'}")
    if absent:
        print(f"    缺失: {', '.join(absent)}")

print()
print("=" * 72)
print("page.on_resize 处理函数签名 / Page 关键方法")
print("=" * 72)
for method in ("show_dialog", "pop_dialog", "add", "update"):
    func = getattr(ft.Page, method, None)
    if func is None:
        print(f"  Page.{method}: 缺失")
        continue
    try:
        print(f"  Page.{method}{inspect.signature(func)}")
    except (TypeError, ValueError):
        print(f"  Page.{method}: 签名不可读")
