#!/usr/bin/env python3
"""Flet API 探针：把实现中要用到的接口在**当前安装版本**里逐个确认。

Flet 近期版本改动过不少命名（版本属性、对话框开关方式、事件名等），
先探测再写代码，避免凭记忆写出装不起来的实现。
"""

from __future__ import annotations

import flet as ft


def has(name: str) -> bool:
    return hasattr(ft, name)


print("=" * 60)
print("版本")
print("=" * 60)
for attr in ("__version__", "version"):
    value = getattr(ft, attr, None)
    if value is not None and not hasattr(value, "__dict__"):
        print(f"  ft.{attr} = {value}")
version_module = getattr(ft, "version", None)
if version_module is not None and hasattr(version_module, "__dict__"):
    for key in ("version", "flutter_version"):
        print(f"  ft.version.{key} = {getattr(version_module, key, '缺失')}")

print()
print("=" * 60)
print("顶层入口")
print("=" * 60)
for name in ("run", "app"):
    print(f"  ft.{name}: {'有' if has(name) else '缺失'}")

print()
print("=" * 60)
print("控件")
print("=" * 60)
controls = (
    "Page", "Column", "Row", "Container", "Stack", "Text", "TextField", "Checkbox",
    "Dropdown", "Button", "ElevatedButton", "FilledButton", "FilledTonalButton",
    "OutlinedButton", "TextButton", "IconButton", "FloatingActionButton",
    "NavigationBar", "NavigationBarDestination", "NavigationDestination",
    "AlertDialog", "GestureDetector", "Card", "ListView", "SafeArea",
    "ProgressRing", "SnackBar", "Divider", "VerticalDivider", "Switch",
    "SegmentedButton", "Segment", "Chip", "Badge", "Stack", "Icon", "Image",
    "DropdownOption", "DropdownM2", "PopupMenuButton", "PopupMenuItem",
)
missing_controls = []
for name in controls:
    ok = has(name)
    if not ok:
        missing_controls.append(name)
    print(f"  {name:<26} {'有' if ok else '缺失'}")

print()
print("=" * 60)
print("枚举与工具")
print("=" * 60)
for name in (
    "Colors", "Icons", "ScrollMode", "MainAxisAlignment", "CrossAxisAlignment",
    "FontWeight", "TextAlign", "TextOverflow", "KeyboardType", "Alignment",
    "ClipBehavior", "StackFit", "BorderRadius", "Border", "BorderSide",
    "padding", "margin", "border_radius", "border", "alignment", "TextStyle",
    "StoragePaths", "DragUpdateEvent", "DragEndEvent", "DragStartEvent",
    "ControlEvent", "TapEvent", "ThemeMode",
):
    print(f"  {name:<26} {'有' if has(name) else '缺失'}")

# 小写下划线风格在旧版里很常见，确认一下当前版本是否还保留
print()
print("  旧式小写别名抽样:")
for name in ("colors", "icons", "padding", "border_radius"):
    print(f"    ft.{name}: {'有' if has(name) else '缺失（新版已移除小写别名）'}")

print()
print("=" * 60)
print("Page 属性")
print("=" * 60)
page_attrs = (
    "show_dialog", "pop_dialog", "dialog", "open", "close", "add", "update",
    "width", "height", "window", "on_resize", "on_resized", "on_keyboard_event",
    "title", "bgcolor", "padding", "spacing", "scroll", "auto_scroll",
    "navigation_bar", "appbar", "theme", "theme_mode", "controls",
    "horizontal_alignment", "vertical_alignment", "platform", "client_storage",
    "shared_preferences", "run_task", "run_thread",
)
for name in page_attrs:
    print(f"  page.{name:<24} {'有' if hasattr(ft.Page, name) else '缺失'}")

print()
print("=" * 60)
print("Container / 布局定位")
print("=" * 60)
for name in ("left", "top", "right", "bottom", "width", "height", "expand",
             "bgcolor", "border_radius", "padding", "on_click", "content",
             "ink", "alignment", "border"):
    print(f"  Container.{name:<16} {'有' if hasattr(ft.Container, name) else '缺失'}")

print()
print("=" * 60)
print("事件对象字段")
print("=" * 60)
for cls_name in ("DragUpdateEvent", "DragEndEvent", "DragStartEvent", "TapEvent"):
    cls = getattr(ft, cls_name, None)
    if cls is None:
        print(f"  {cls_name}: 缺失")
        continue
    fields = [f for f in ("local_delta", "global_delta", "local_position",
                          "global_position", "primary_velocity", "velocity",
                          "control", "page", "name") if hasattr(cls, f)]
    print(f"  {cls_name}: {fields}")

print()
print("=" * 60)
print("StoragePaths 方法")
print("=" * 60)
paths_cls = getattr(ft, "StoragePaths", None)
if paths_cls is None:
    print("  缺失")
else:
    for name in ("get_application_documents_directory",
                 "get_application_support_directory",
                 "get_application_cache_directory"):
        print(f"  {name}: {'有' if hasattr(paths_cls, name) else '缺失'}")

print()
print("=" * 60)
print("结论")
print("=" * 60)
if missing_controls:
    print("  缺失控件:", ", ".join(missing_controls))
else:
    print("  实现所需的控件全部可用")
