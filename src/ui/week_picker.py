"""周次多选组件。

做成类而不是函数，是为了让宿主（课程表单）能随时取回当前选中的周次，
而不必依赖闭包变量来回传值。
"""

from __future__ import annotations

from collections.abc import Callable

import flet as ft

from core import week_engine
from ui import layout


class WeekPicker:
    """1..total_weeks 的复选网格，附带全选 / 单周 / 双周 / 清空快捷操作。"""

    def __init__(
        self,
        page: ft.Page,
        total_weeks: int,
        selected: list[int] | None = None,
        on_change: Callable[[list[int]], None] | None = None,
    ) -> None:
        self.page = page
        self.total_weeks = max(1, total_weeks)
        self.selected: set[int] = {w for w in (selected or []) if 1 <= w <= self.total_weeks}
        self.on_change = on_change
        self._boxes: dict[int, ft.Checkbox] = {}
        self._summary: ft.Text | None = None

    # ------------------------------------------------------------------ #
    # 取值 / 设值
    # ------------------------------------------------------------------ #

    def value(self) -> list[int]:
        return sorted(self.selected)

    def set_value(self, weeks: list[int]) -> None:
        self.selected = {w for w in weeks if 1 <= w <= self.total_weeks}
        for week, box in self._boxes.items():
            box.value = week in self.selected
            box.update()
        self._refresh_summary()

    # ------------------------------------------------------------------ #
    # 内部
    # ------------------------------------------------------------------ #

    def _notify(self) -> None:
        """统一出口：刷新摘要文案，再通知宿主。"""
        self._refresh_summary()
        if self.on_change:
            self.on_change(self.value())

    def _refresh_summary(self) -> None:
        summary = self._summary
        # 控件尚未挂载到页面时不能 update，直接跳过即可（纯显示性文案）
        if summary is None or not layout.is_on_page(summary):
            return
        summary.value = self._summary_text()
        summary.update()

    def _summary_text(self) -> str:
        weeks = self.value()
        if not weeks:
            return "未选择任何周次"
        return f"已选 {len(weeks)} 周：{week_engine.format_weeks(weeks)}"

    def _toggle(self, week: int, checked: bool) -> None:
        if checked:
            self.selected.add(week)
        else:
            self.selected.discard(week)
        self._notify()

    def _apply(self, weeks: list[int]) -> None:
        self.selected = {w for w in weeks if 1 <= w <= self.total_weeks}
        for week, box in self._boxes.items():
            box.value = week in self.selected
            box.update()
        self._notify()

    def _build_box(self, week: int) -> ft.Checkbox:
        def handle(event: ft.ControlEvent, target: int = week) -> None:
            self._toggle(target, bool(event.control.value))

        box = ft.Checkbox(
            label=str(week),
            value=week in self.selected,
            width=54,
            label_style=ft.TextStyle(size=12),
            on_change=handle,
        )
        self._boxes[week] = box
        return box

    # ------------------------------------------------------------------ #
    # 构建
    # ------------------------------------------------------------------ #

    def control(self) -> ft.Control:
        self._boxes.clear()
        self._summary = ft.Text(self._summary_text(), size=11, color=ft.Colors.GREY_700)

        quick = ft.Row(
            spacing=6,
            wrap=True,
            controls=[
                ft.Button(
                    content="全选",
                    on_click=lambda _e: self._apply(list(range(1, self.total_weeks + 1))),
                ),
                ft.Button(
                    content="单周",
                    on_click=lambda _e: self._apply(list(range(1, self.total_weeks + 1, 2))),
                ),
                ft.Button(
                    content="双周",
                    on_click=lambda _e: self._apply(list(range(2, self.total_weeks + 1, 2))),
                ),
                ft.Button(content="清空", on_click=lambda _e: self._apply([])),
            ],
        )

        grid = ft.Row(
            spacing=0,
            run_spacing=0,
            wrap=True,
            controls=[self._build_box(week) for week in range(1, self.total_weeks + 1)],
        )

        return ft.Column(spacing=6, controls=[quick, grid, self._summary])
