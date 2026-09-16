"""学期设置：总周数、开学日期、每天节数与各节起止时间。

保存后由 AppState 落盘并广播，界面重建即显示新值。
"""

from __future__ import annotations

from datetime import date, timedelta

import flet as ft

from core import config, storage
from core.models import SemesterSettings
from state import AppState
from ui import layout


def _parse_int(value: str | None) -> int | None:
    try:
        return int((value or "").strip())
    except (TypeError, ValueError):
        return None


def _parse_date(value: str | None) -> date | None:
    try:
        return date.fromisoformat((value or "").strip())
    except (TypeError, ValueError):
        return None


def build_settings_view(page: ft.Page, state: AppState) -> ft.Control:
    settings = state.settings

    error_text = ft.Text("", size=12, color=ft.Colors.RED, visible=False)

    def show_error(message: str) -> None:
        error_text.value = message
        error_text.visible = True
        error_text.update()

    # ---- 学期基本信息 ----

    weeks_field = ft.TextField(
        label="本学期总周数",
        value=str(settings.total_weeks),
        keyboard_type=ft.KeyboardType.NUMBER,
        text_size=14,
        width=150,
        border=layout.input_border(),
        helper=f"可填 {config.MIN_TOTAL_WEEKS}-{config.MAX_TOTAL_WEEKS}",
    )

    start_field = ft.TextField(
        label="开学日期（第 1 周的周一）",
        value=settings.start_date_obj().isoformat(),
        text_size=14,
        expand=True,
        border=layout.input_border(),
        helper="格式 2026-09-07",
    )

    slots_field = ft.TextField(
        label="每天节数",
        value=str(settings.slots_per_day),
        keyboard_type=ft.KeyboardType.NUMBER,
        text_size=14,
        width=150,
        border=layout.input_border(),
        helper=f"可填 {config.MIN_SLOTS_PER_DAY}-{config.MAX_SLOTS_PER_DAY}",
    )

    # ---- 节次时间行（随"每天节数"重建）----

    time_rows = ft.Column(spacing=6, controls=[])
    time_fields: list[tuple[int, ft.TextField, ft.TextField]] = []

    def rebuild_time_rows(count: int, values: list[list[str]] | None = None) -> None:
        """按节数重建时间输入行。values 为空时沿用当前设置里的时间。"""
        time_fields.clear()
        rows: list[ft.Control] = []
        source = values if values is not None else settings.slot_times
        for slot in range(1, count + 1):
            if slot - 1 < len(source) and len(source[slot - 1]) >= 2:
                start_value, end_value = source[slot - 1][0], source[slot - 1][1]
            elif slot - 1 < len(config.DEFAULT_SLOT_TIMES):
                start_value, end_value = config.DEFAULT_SLOT_TIMES[slot - 1]
            else:
                start_value, end_value = "", ""

            start_input = ft.TextField(value=start_value, text_size=13, width=86,
                                       border=layout.input_border(), hint_text="08:00")
            end_input = ft.TextField(value=end_value, text_size=13, width=86,
                                     border=layout.input_border(), hint_text="08:45")
            time_fields.append((slot, start_input, end_input))
            rows.append(
                ft.Row(
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Text(f"第{slot}节", size=12, width=48),
                        start_input,
                        ft.Text("—", size=12),
                        end_input,
                    ],
                )
            )
        time_rows.controls = rows

    def handle_slots_change(event: ft.ControlEvent) -> None:
        """节数变化时立即重建行数，避免保存时才发现对不上。"""
        count = _parse_int(event.control.value)
        if count is None or not (config.MIN_SLOTS_PER_DAY <= count <= config.MAX_SLOTS_PER_DAY):
            return
        current = [[field[1].value or "", field[2].value or ""] for field in time_fields]
        rebuild_time_rows(count, current)
        time_rows.update()

    slots_field.on_change = handle_slots_change
    rebuild_time_rows(settings.slots_per_day)

    def fill_default_times(_event: ft.ControlEvent) -> None:
        rebuild_time_rows(len(time_fields), [list(pair) for pair in config.DEFAULT_SLOT_TIMES])
        time_rows.update()

    def set_start_today(_event: ft.ControlEvent) -> None:
        start_field.value = date.today().isoformat()
        start_field.update()

    def set_start_monday(_event: ft.ControlEvent) -> None:
        today = date.today()
        monday = today - timedelta(days=today.isoweekday() - 1)
        start_field.value = monday.isoformat()
        start_field.update()

    # ---- 保存 ----

    def save(_event: ft.ControlEvent) -> None:
        if error_text.visible:
            error_text.visible = False
            error_text.update()

        total = _parse_int(weeks_field.value)
        if total is None or not (config.MIN_TOTAL_WEEKS <= total <= config.MAX_TOTAL_WEEKS):
            show_error(f"总周数需为 {config.MIN_TOTAL_WEEKS}-{config.MAX_TOTAL_WEEKS} 之间的整数")
            return

        slots = _parse_int(slots_field.value)
        if slots is None or not (config.MIN_SLOTS_PER_DAY <= slots <= config.MAX_SLOTS_PER_DAY):
            show_error(f"每天节数需为 {config.MIN_SLOTS_PER_DAY}-{config.MAX_SLOTS_PER_DAY} 之间的整数")
            return

        start = _parse_date(start_field.value)
        if start is None:
            show_error("开学日期格式不正确，应为 YYYY-MM-DD，例如 2026-09-07")
            return

        if len(time_fields) != slots:
            show_error("节次时间行数与每天节数不一致，请重新选择每天节数")
            return

        slot_times = [[start_input.value or "", end_input.value or ""] for _, start_input, end_input in time_fields]

        updated = SemesterSettings(
            total_weeks=total,
            start_date=start.isoformat(),
            slots_per_day=slots,
            slot_times=slot_times,
        )
        updated.normalize()
        # 落盘 + 广播，界面随之重建，新值即为反馈
        state.update_settings(updated)
        state.set_flash("学期设置已保存")

    # ---- 组装 ----

    data_path = storage.data_file()

    return ft.Column(
        spacing=14,
        scroll=ft.ScrollMode.AUTO,
        controls=[
            ft.Text("学期设置", size=18, weight=ft.FontWeight.BOLD),
            weeks_field,
            ft.Row(
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Container(content=start_field, expand=True),
                ],
            ),
            ft.Row(
                spacing=8,
                wrap=True,
                controls=[
                    ft.Button(content="今天", on_click=set_start_today),
                    ft.Button(content="本周一", on_click=set_start_monday),
                ],
            ),
            ft.Divider(height=1),
            slots_field,
            ft.Row(
                spacing=8,
                wrap=True,
                controls=[
                    ft.Text("各节起止时间", size=14, weight=ft.FontWeight.W_500),
                    ft.Button(content="恢复默认时间", on_click=fill_default_times),
                ],
            ),
            time_rows,
            error_text,
            ft.Button(content="保存设置", icon=ft.Icons.SAVE, on_click=save),
            ft.Divider(height=1),
            ft.Text("数据文件", size=13, weight=ft.FontWeight.W_500),
            ft.Text(str(data_path), size=11, color=ft.Colors.GREY_700, selectable=True),
        ],
    )
