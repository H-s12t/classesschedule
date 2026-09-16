"""应用外壳：底部导航 + 视图调度 + 状态广播的落点。

各视图都是"每次刷新重建"的函数式构造，而不是增量更新控件。
课程数据规模很小（一学期几十门课），重建成本可以忽略，
换来的是不存在"数据变了但某个控件忘了同步"这类问题。
"""

from __future__ import annotations

from datetime import date

import flet as ft

from core import config
from core.models import Course
from state import AppState
from ui import layout
from ui.course_form import open_course_form
from ui.day_view import build_day_view
from ui.schedule_view import build_schedule_view
from ui.settings_view import build_settings_view

TAB_SCHEDULE = 0
TAB_DAY = 1
TAB_SETTINGS = 2


class AppShell:
    def __init__(self, page: ft.Page, state: AppState) -> None:
        self.page = page
        self.state = state
        self.tab = TAB_SCHEDULE
        self._last_width = 0.0

        self._content = ft.Container(expand=True)
        self._banner_text = ft.Text("", size=12, color="#1B5E20")
        self._banner = ft.Container(
            visible=False,
            bgcolor="#E8F5E9",
            border_radius=ft.BorderRadius.all(6),
            padding=ft.Padding.symmetric(horizontal=8, vertical=6),
            content=self._banner_text,
        )
        self._inner = ft.Column(
            spacing=6,
            expand=True,
            controls=[self._banner, self._content],
        )
        self._nav = ft.NavigationBar(
            selected_index=self.tab,
            on_change=self._on_nav_change,
            destinations=[
                ft.NavigationBarDestination(icon=ft.Icons.CALENDAR_MONTH, label="课表"),
                ft.NavigationBarDestination(icon=ft.Icons.EVENT, label="单日"),
                ft.NavigationBarDestination(icon=ft.Icons.SETTINGS, label="设置"),
            ],
        )

    # ------------------------------------------------------------------ #
    # 构建
    # ------------------------------------------------------------------ #

    def build(self) -> ft.Control:
        """构建控件树。此时尚未挂载，只渲染不 update。"""
        self._render_banner()
        self._render_tab()
        return ft.Column(
            spacing=0,
            expand=True,
            controls=[
                ft.Container(
                    expand=True,
                    padding=ft.Padding.symmetric(
                        horizontal=config.CONTENT_PADDING, vertical=6
                    ),
                    content=self._inner,
                ),
                self._nav,
            ],
        )

    def on_mounted(self) -> None:
        """兼容入口的收尾调用；挂载与否由 layout.is_on_page() 自行判断。"""
        self.refresh()

    # ------------------------------------------------------------------ #
    # 刷新
    # ------------------------------------------------------------------ #

    def refresh(self) -> None:
        """状态广播的落点：重建当前页，并同步导航栏与提示条。"""
        self._nav.selected_index = self.tab
        self._render_banner()
        self._render_tab()

        # 尚未挂载到页面时不能 update（build() 期间会走到这里）。
        # 用 layout.is_on_page 而不是 `control.page is None`：后者未挂载时会抛异常。
        if not layout.is_on_page(self._content):
            return
        self._content.update()
        self._banner.update()
        self._nav.update()

    def _render_banner(self) -> None:
        message = self.state.take_flash()
        if message:
            self._banner_text.value = message
            self._banner.visible = True
        else:
            self._banner.visible = False

    def _render_tab(self) -> None:
        if self.tab == TAB_DAY:
            view: ft.Control = build_day_view(
                self.page, self.state, self._add_course_at, self._edit_course
            )
        elif self.tab == TAB_SETTINGS:
            view = build_settings_view(self.page, self.state)
        else:
            view = build_schedule_view(
                self.page, self.state, self._open_day, self._edit_course
            )
        self._content.content = view

    # ------------------------------------------------------------------ #
    # 交互
    # ------------------------------------------------------------------ #

    def _on_nav_change(self, event: ft.ControlEvent) -> None:
        self.tab = int(event.control.selected_index)
        self.refresh()

    def _open_day(self, day: date) -> None:
        """周视图点某天列：定位到该日并切到单日视图。

        先改选中日期再切页，保证重建时单日视图拿到的已经是目标日期。
        """
        self.state.select_date(day)
        self.tab = TAB_DAY
        self.refresh()

    def _add_course_at(self, day: date, slot: int) -> None:
        """单日视图点空白节次：预填星期与节次，用户只需填课名。"""
        open_course_form(
            self.page,
            self.state,
            prefill={
                "weekday": day.isoweekday(),
                "start_slot": slot,
                "end_slot": slot,
            },
        )

    def _edit_course(self, course: Course) -> None:
        open_course_form(self.page, self.state, course=course)

    # ------------------------------------------------------------------ #
    # 窗口尺寸变化
    # ------------------------------------------------------------------ #

    def on_resize(self, _event: ft.ControlEvent | None = None) -> None:
        """宽度变化时重算列宽。

        首次布局会把宽度从 0 变为真实值，因此这里也承担"补一次重绘"的职责；
        宽度没实质变化时直接跳过，避免无意义的反复重建。
        """
        width = layout.page_width(self.page)
        if abs(width - self._last_width) < 2:
            return
        self._last_width = width

        # 设置页的布局不依赖列宽换算（用的是 expand 与固定宽度），
        # 重建只会白白丢掉用户正在输入的内容 —— 所以它不需要响应宽度变化。
        # 周视图与单日视图的列宽、课程块宽度要按新宽度重算，必须重建。
        if self.tab == TAB_SETTINGS:
            return
        self.refresh()
