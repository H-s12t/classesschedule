"""单节课备注编辑弹层。

这里的备注与课程级备注（`Course.note`）是**并存**关系，不是覆盖：
- 课程级备注在「编辑课程」里填写，默认作用于这门课的所有上课时间；
- 本弹层改的是"这一天这一节课"的备注，只影响单节课。
两者会同时出现在单日视图的课程块里，所以这里顺带把课程级备注展示出来，
让用户清楚"哪些是这门课本来就带的、哪些是我这次临时加的"。
"""

from __future__ import annotations

from datetime import date
from typing import Callable

import flet as ft

from core import config
from core.models import Course
from state import AppState
from ui import layout

_DIALOG_MAX_WIDTH = 340


def _dialog_width(page: ft.Page) -> float:
    """弹层宽度：窄屏（手机）时收窄，避免超出可视区域。"""
    width = _DIALOG_MAX_WIDTH
    page_width = float(getattr(page, "width", 0) or 0)
    if page_width > 1:
        width = max(240.0, min(_DIALOG_MAX_WIDTH, page_width - 40.0))
    return width


def open_note_form(
    page: ft.Page,
    state: AppState,
    day: date,
    course: Course,
    on_saved: Callable[[], None] | None = None,
) -> None:
    """打开"本节课备注"弹层。"""
    existing = state.session_note(day, course)

    head = ft.Column(
        spacing=2,
        controls=[
            ft.Text(course.name, size=15, weight=ft.FontWeight.W_500),
            ft.Text(
                f"{day.month}月{day.day}日 · 第{course.start_slot}-{course.end_slot}节",
                size=12,
                color=ft.Colors.GREY_700,
            ),
        ],
    )

    if course.note:
        inherited_text = f"{config.NOTE_MARK_COURSE}备注：{course.note}"
    else:
        inherited_text = f"{config.NOTE_MARK_COURSE}备注：未填写（可在「编辑课程」里添加）"
    inherited = ft.Text(
        inherited_text,
        size=11,
        color=ft.Colors.GREY_700,
        max_lines=3,
        overflow=ft.TextOverflow.ELLIPSIS,
    )

    field = ft.TextField(
        label=f"{config.NOTE_MARK_SESSION}备注",
        value=existing,
        text_size=14,
        multiline=True,
        min_lines=2,
        max_lines=4,
        max_length=config.MAX_NOTE_LENGTH,
        hint_text="仅影响这一天这节课，例如：本周交作业",
        border=layout.input_border(),
    )

    def save(_event: ft.ControlEvent) -> None:
        state.set_session_note(day, course, field.value or "")
        page.pop_dialog()
        if on_saved:
            on_saved()

    def clear(_event: ft.ControlEvent) -> None:
        state.set_session_note(day, course, "")
        page.pop_dialog()
        if on_saved:
            on_saved()

    # 「清除」只在已有备注时出现，免得空白备注的课上多一个按了没反应的按钮
    actions = [ft.TextButton(content="取消", on_click=lambda _e: page.pop_dialog())]
    if existing:
        actions.append(ft.TextButton(content="清除本节备注", on_click=clear))
    actions.append(ft.Button(content="保存", icon=ft.Icons.CHECK, on_click=save))

    body = ft.Column(
        spacing=10,
        scroll=ft.ScrollMode.AUTO,
        controls=[head, ft.Divider(height=1), inherited, field],
    )

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("本节课备注"),
        content=ft.Container(width=_dialog_width(page), content=body),
        actions=actions,
    )
    page.show_dialog(dialog)
