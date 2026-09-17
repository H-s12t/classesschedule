"""单日视图：选定日期的 12 节纵向列表。

与周视图的分工：
- 列宽充足，因此承担详细信息展示（课名、地点、教师、节次范围、每节起止时间）
- 翻页**只用按钮**，不接横向手势 —— 滑动翻页专属周视图，避免手势通道竞争
- 点空白节次直接新增课程，并预填该星期与该节次
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

import flet as ft

from core import config
from core.models import Course
from state import AppState
from ui import layout


def build_day_view(
    page: ft.Page,
    state: AppState,
    on_add_at: Callable[[date, int], None],
    on_edit_course: Callable[[Course], None],
    on_edit_note: Callable[[date, Course], None],
) -> ft.Control:
    settings = state.settings
    slots = settings.slots_per_day
    day = state.selected_date
    week = state.current_week
    is_today = day == date.today()

    row_height = config.DAY_ROW_HEIGHT
    body_width = max(layout.content_width(page) - config.DAY_TIME_COL_WIDTH, 120.0)

    # ---------------- 日期导航（仅按钮）----------------

    def shift(delta: int) -> None:
        if state.can_shift_day(delta):
            state.shift_days(delta)
            state.refresh()

    def back_to_today(_event: ft.ControlEvent) -> None:
        state.go_today()
        state.refresh()

    weekday_name = config.WEEKDAY_NAMES[day.isoweekday() - 1]
    nav = ft.Row(
        spacing=0,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.IconButton(
                icon=ft.Icons.CHEVRON_LEFT,
                tooltip="前一天",
                disabled=not state.can_shift_day(-1),
                on_click=lambda _e: shift(-1),
            ),
            ft.Container(
                expand=True,
                alignment=ft.Alignment.CENTER,
                content=ft.Column(
                    spacing=0,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Text(
                            f"{day.month}月{day.day}日 {weekday_name}"
                            + ("（今天）" if is_today else ""),
                            size=15,
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Text(f"第 {week} 周", size=11, color=ft.Colors.GREY_700),
                    ],
                ),
            ),
            ft.IconButton(
                icon=ft.Icons.CHEVRON_RIGHT,
                tooltip="后一天",
                disabled=not state.can_shift_day(1),
                on_click=lambda _e: shift(1),
            ),
        ],
    )

    actions = ft.Row(
        spacing=8,
        controls=[
            ft.Button(content="回到今天", icon=ft.Icons.TODAY, on_click=back_to_today),
            ft.Text("单击课程块改本节备注，长按改课程", size=10, color=ft.Colors.GREY_700),
        ],
    )

    # ---------------- 左侧：节次与时间 ----------------

    total_height = row_height * slots

    time_cells: list[ft.Control] = []
    for slot in range(1, slots + 1):
        start_time, end_time = settings.slot_time(slot)
        time_cells.append(
            ft.Container(
                left=0,
                top=(slot - 1) * row_height,
                width=config.DAY_TIME_COL_WIDTH,
                height=row_height,
                bgcolor=layout.HEADER_BG,
                alignment=ft.Alignment.CENTER,
                content=ft.Column(
                    spacing=0,
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Text(f"第{slot}节", size=11, weight=ft.FontWeight.W_500),
                        ft.Text(
                            f"{start_time} {end_time}" if start_time or end_time else "",
                            size=9,
                            color=ft.Colors.GREY_700,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ],
                ),
            )
        )

    time_column = ft.Stack(
        width=config.DAY_TIME_COL_WIDTH,
        height=total_height,
        controls=[
            *time_cells,
            *layout.horizontal_separators(row_height, slots, config.DAY_TIME_COL_WIDTH),
            layout.vertical_separator(config.DAY_TIME_COL_WIDTH, total_height),
        ],
    )

    # ---------------- 右侧：课程块 ----------------

    children: list[ft.Control] = []
    for slot in range(1, slots + 1):
        # 这一层同时充当背景与"点空白新增"的命中区域
        children.append(
            ft.Container(
                left=0,
                top=(slot - 1) * row_height,
                width=body_width,
                height=row_height,
                bgcolor=layout.slot_background(slot, False),
                ink=True,
                on_click=lambda _e, target=slot: on_add_at(day, target),
            )
        )

    children.extend(layout.horizontal_separators(row_height, slots, body_width))

    # 课程块后加，因此浮在命中区域之上：点课程块是编辑备注，长按是编辑课程，点空白是新增
    blocks = state.blocks_for(day)
    for block in blocks:
        lesson: Course = block["course"]
        children.append(
            layout.course_block(
                block,
                body_width,
                row_height,
                on_click=lambda target, d=day: on_edit_note(d, target),
                on_long_press=on_edit_course,
                detailed=True,
                # 两条备注并存：课程级的通用说明 + 这一节的临时补充
                notes=(lesson.note, state.session_note(day, lesson)),
            )
        )

    body = ft.Row(
        spacing=0,
        controls=[
            time_column,
            ft.Stack(width=body_width, height=total_height, controls=children),
        ],
    )

    hint = (
        ft.Text("这一天没有课", size=13, color=ft.Colors.GREY_700)
        if not blocks
        else ft.Text(f"共 {len(blocks)} 门课", size=11, color=ft.Colors.GREY_700)
    )

    grid = ft.Column(spacing=0, expand=True, scroll=ft.ScrollMode.AUTO, controls=[body])

    return ft.Column(spacing=6, expand=True, controls=[nav, actions, hint, grid])
