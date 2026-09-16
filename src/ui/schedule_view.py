"""周视图：表头 + 7 列 × N 节的网格，课程块按节次绝对定位。

列宽由内容区宽度均分而来，行高是常量，因此课程块的 top / height 只取决于节次，
与屏幕尺寸无关 —— 这是跨节次课程能稳定占满整段的原因。
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

import flet as ft

from core import config, week_engine
from state import AppState
from ui import layout


def _shift(state: AppState, delta: int) -> None:
    """翻页。越界时静默忽略，按钮此时本来就是禁用态。"""
    if state.can_shift_week(delta):
        state.shift_weeks(delta)
        state.refresh()


def build_schedule_view(
    page: ft.Page,
    state: AppState,
    on_pick_day: Callable[[date], None],
    on_edit_course: Callable[[object], None],
) -> ft.Control:
    settings = state.settings
    slots = settings.slots_per_day
    total_weeks = settings.total_weeks
    week = state.current_week
    days = state.week_dates(week)
    today = date.today()

    available = layout.content_width(page)
    column_width = max((available - config.TIME_COL_WIDTH) / 7, 24.0)
    row_height = config.WEEK_ROW_HEIGHT

    # ---------------- 表头 ----------------

    header_cells: list[ft.Control] = [
        ft.Container(
            width=config.TIME_COL_WIDTH,
            height=config.WEEK_HEADER_HEIGHT,
            bgcolor=layout.HEADER_BG,
            alignment=ft.Alignment.CENTER,
            content=ft.Text("节次", size=10, color=layout.TEXT_ON_HEADER),
        )
    ]
    for index, day in enumerate(days):
        is_today = day == today
        header_cells.append(
            ft.Container(
                width=column_width,
                height=config.WEEK_HEADER_HEIGHT,
                bgcolor=layout.TODAY_HEADER_BG if is_today else layout.HEADER_BG,
                alignment=ft.Alignment.CENTER,
                ink=True,
                # 点某天列 = 直接切到那天的单日视图
                on_click=lambda _e, target=day: on_pick_day(target),
                content=ft.Column(
                    spacing=0,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Text(
                            config.WEEKDAY_NAMES[index],
                            size=10,
                            color=ft.Colors.WHITE if is_today else layout.TEXT_ON_HEADER,
                        ),
                        ft.Text(
                            f"{day.month}/{day.day}",
                            size=10,
                            color=ft.Colors.WHITE if is_today else layout.TEXT_ON_HEADER,
                        ),
                    ],
                ),
            )
        )
    header = ft.Row(spacing=0, controls=header_cells)

    # ---------------- 主体 ----------------

    time_cells: list[ft.Control] = []
    for slot in range(1, slots + 1):
        start_time, end_time = settings.slot_time(slot)
        time_cells.append(
            ft.Container(
                width=config.TIME_COL_WIDTH,
                height=row_height,
                bgcolor=layout.HEADER_BG,
                alignment=ft.Alignment.CENTER,
                content=ft.Column(
                    spacing=0,
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Text(str(slot), size=11, weight=ft.FontWeight.W_500),
                        ft.Text(start_time, size=8, color=ft.Colors.GREY_700),
                        ft.Text(end_time, size=8, color=ft.Colors.GREY_700),
                    ],
                ),
            )
        )

    weekly_blocks = state.blocks_of_week(week)
    total_height = row_height * slots

    day_columns: list[ft.Control] = []
    for index, day in enumerate(days):
        is_weekend = day.isoweekday() >= 6
        children: list[ft.Control] = []

        # 先铺背景（同时充当此列的视觉网格）
        for slot in range(1, slots + 1):
            children.append(
                ft.Container(
                    left=0,
                    top=(slot - 1) * row_height,
                    width=column_width - 1,
                    height=row_height,
                    bgcolor=layout.slot_background(slot, is_weekend),
                )
            )

        # 行分隔线与列分隔线：没有它们，交替色在手机上仍不足以分辨行次
        children.extend(layout.horizontal_separators(row_height, slots, column_width - 1))
        children.append(layout.vertical_separator(column_width, total_height))

        # 最后叠课程块（LIFO，后加的在上层）
        for block in weekly_blocks.get(day.isoweekday(), []):
            children.append(
                layout.course_block(block, column_width, row_height, on_click=on_edit_course)
            )

        day_columns.append(
            ft.Stack(width=column_width, height=total_height, controls=children)
        )

    body = ft.Row(spacing=0, controls=[ft.Column(spacing=0, controls=time_cells), *day_columns])

    # 12 节在手机上放不下，必须可纵向滚动
    grid = ft.Column(spacing=0, expand=True, scroll=ft.ScrollMode.AUTO, controls=[body])

    # ---------------- 横向滑动翻页 ----------------
    # 只累加横向位移，超过阈值才翻页，避免和纵向滚动抢手势
    drag_tracker = {"dx": 0.0}

    def on_drag_start(_event: ft.ControlEvent) -> None:
        drag_tracker["dx"] = 0.0

    def on_drag_update(event: ft.ControlEvent) -> None:
        drag_tracker["dx"] += float(getattr(event, "local_delta").x)

    def on_drag_end(_event: ft.ControlEvent) -> None:
        dx = drag_tracker["dx"]
        drag_tracker["dx"] = 0.0
        if abs(dx) < config.SWIPE_THRESHOLD:
            return
        # 向左滑 = 看下一周
        _shift(state, 1 if dx < 0 else -1)

    detector = ft.GestureDetector(
        expand=True,
        drag_interval=20,
        on_horizontal_drag_start=on_drag_start,
        on_horizontal_drag_update=on_drag_update,
        on_horizontal_drag_end=on_drag_end,
        content=grid,
    )

    # ---------------- 周次导航条 ----------------

    relative = week_engine.relative_week_label(settings.start_date_obj(), total_weeks, week)
    nav = ft.Row(
        spacing=0,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.IconButton(
                icon=ft.Icons.CHEVRON_LEFT,
                tooltip="上一周",
                disabled=not state.can_shift_week(-1),
                on_click=lambda _e: _shift(state, -1),
            ),
            ft.Container(
                expand=True,
                alignment=ft.Alignment.CENTER,
                content=ft.Column(
                    spacing=0,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Text(f"第 {week} 周（共 {total_weeks} 周）", size=15,
                                weight=ft.FontWeight.BOLD),
                        ft.Text(f"{state.week_range_text(week)} · {relative}", size=11,
                                color=ft.Colors.GREY_700),
                    ],
                ),
            ),
            ft.IconButton(
                icon=ft.Icons.CHEVRON_RIGHT,
                tooltip="下一周",
                disabled=not state.can_shift_week(1),
                on_click=lambda _e: _shift(state, 1),
            ),
        ],
    )

    def back_to_today(_event: ft.ControlEvent) -> None:
        state.go_today()
        state.refresh()

    actions = ft.Row(
        spacing=8,
        controls=[
            ft.Button(content="回到今天", icon=ft.Icons.TODAY, on_click=back_to_today),
            ft.Text("点某天可切到单日视图", size=10, color=ft.Colors.GREY_700),
        ],
    )

    return ft.Column(
        spacing=6,
        expand=True,
        controls=[nav, actions, header, detector],
    )
