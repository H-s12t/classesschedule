"""课程新增 / 编辑表单（弹层）。

被周视图与单日视图共同调用。单日视图点空白节次时会传入 prefill，
把星期和起止节次预先填好，用户只需填课名。

表单里刻意不使用 SnackBar 做校验提示，而是在弹层内放一行错误文案 ——
提示位置离出错的输入框更近，也不依赖对话框与 SnackBar 的层叠行为。
"""

from __future__ import annotations

from collections.abc import Callable

import flet as ft

from core import config
from core.models import Course
from state import AppState
from ui import layout
from ui.week_picker import WeekPicker

_FORM_MAX_WIDTH = 340
_FORM_MAX_HEIGHT = 470
# 对话框还要容纳标题与按钮行，内容区最多占页面高度的这个比例
_FORM_HEIGHT_RATIO = 0.70


def _form_size(page: ft.Page) -> tuple[float, float]:
    """按页面尺寸算出表单内容区大小。

    高度若写死，在矮视口（手机横屏、小屏机型）上内容会被裁掉，
    底部的颜色与周次选择够不到。这里按页面高度收缩，并保留一个下限以免小到没法用。
    """
    try:
        page_height = float(getattr(page, "height", 0) or 0)
        page_width = float(getattr(page, "width", 0) or 0)
    except (TypeError, ValueError):
        page_height = page_width = 0.0

    height = _FORM_MAX_HEIGHT
    if page_height > 1:
        height = max(220.0, min(_FORM_MAX_HEIGHT, page_height * _FORM_HEIGHT_RATIO))

    width = _FORM_MAX_WIDTH
    if page_width > 1:
        width = max(240.0, min(_FORM_MAX_WIDTH, page_width - 40.0))

    return width, height


def open_course_form(
    page: ft.Page,
    state: AppState,
    course: Course | None = None,
    prefill: dict | None = None,
    on_saved: Callable[[Course], None] | None = None,
) -> None:
    """打开表单。course 为空表示新增，否则为编辑。"""
    prefill = prefill or {}
    settings = state.settings
    slots = settings.slots_per_day
    is_edit = course is not None

    # ---- 初始值 ----
    if is_edit:
        init_name = course.name
        init_weekday = course.weekday
        init_start = course.start_slot
        init_end = course.end_slot
        init_location = course.location
        init_teacher = course.teacher
        init_note = course.note
        init_color = course.color
        init_weeks = list(course.weeks)
    else:
        init_name = ""
        init_weekday = int(prefill.get("weekday", 1))
        init_start = int(prefill.get("start_slot", 1))
        init_end = int(prefill.get("end_slot", init_start))
        init_location = ""
        init_teacher = ""
        init_note = ""
        init_color = state.next_course_color()
        # 新增课程默认整学期都上，用户再按需取消，比从零开始勾更省事
        init_weeks = list(prefill.get("weeks") or range(1, settings.total_weeks + 1))

    init_weekday = min(max(init_weekday, 1), 7)
    init_start = min(max(init_start, 1), slots)
    init_end = min(max(init_end, init_start), slots)
    if init_end < init_start:
        init_end = init_start

    # ---- 控件 ----
    name_field = ft.TextField(
        label="课程名称",
        value=init_name,
        autofocus=False,
        text_size=14,
        border=layout.input_border(),
    )

    weekday_dropdown = ft.Dropdown(
        label="星期",
        value=str(init_weekday),
        text_size=14,
        options=[
            ft.DropdownOption(key=str(day), text=config.WEEKDAY_NAMES[day - 1])
            for day in range(1, 8)
        ],
    )

    start_dropdown = ft.Dropdown(
        label="起始节次",
        value=str(init_start),
        text_size=14,
        expand=True,
        options=[ft.DropdownOption(key=str(slot), text=f"第{slot}节") for slot in range(1, slots + 1)],
    )

    end_dropdown = ft.Dropdown(
        label="结束节次",
        value=str(init_end),
        text_size=14,
        expand=True,
        options=[ft.DropdownOption(key=str(slot), text=f"第{slot}节") for slot in range(1, slots + 1)],
    )

    location_field = ft.TextField(
        label="上课地点",
        value=init_location,
        text_size=14,
        border=layout.input_border(),
    )

    teacher_field = ft.TextField(
        label="任课教师",
        value=init_teacher,
        text_size=14,
        border=layout.input_border(),
    )

    # 课程级备注：默认作用于这门课的**所有**上课时间（与单日视图里的单节备注并存）
    note_field = ft.TextField(
        label=f"{config.NOTE_MARK_COURSE}备注",
        value=init_note,
        text_size=14,
        multiline=True,
        min_lines=2,
        max_lines=3,
        max_length=config.MAX_NOTE_LENGTH,
        hint_text="默认作用于这门课的所有上课时间，例如：需带计算器",
        border=layout.input_border(),
    )

    error_text = ft.Text("", size=12, color=ft.Colors.RED, visible=False)

    def show_error(message: str) -> None:
        error_text.value = message
        error_text.visible = True
        error_text.update()

    def clear_error() -> None:
        if error_text.visible:
            error_text.visible = False
            error_text.update()

    # 起始节次后移时把结束节次一起顶上去，从根上避免出现"结束早于开始"的非法状态
    def handle_start_change(event: ft.ControlEvent) -> None:
        clear_error()
        start = int(event.control.value)
        if int(end_dropdown.value or "1") < start:
            end_dropdown.value = str(start)
            end_dropdown.update()

    start_dropdown.on_select = handle_start_change
    end_dropdown.on_select = lambda _e: clear_error()
    weekday_dropdown.on_select = lambda _e: clear_error()

    # ---- 颜色选择 ----
    selected_color = [init_color]
    swatches: list[tuple[str, ft.Container]] = []

    def pick_color(color: str) -> None:
        selected_color[0] = color
        for value, container in swatches:
            container.content = (
                ft.Icon(ft.Icons.CHECK, size=16, color=ft.Colors.WHITE) if value == color else None
            )
            container.update()

    def make_swatch(color: str) -> ft.Container:
        container = ft.Container(
            width=30,
            height=30,
            bgcolor=color,
            border_radius=ft.BorderRadius.all(15),
            alignment=ft.Alignment.CENTER,
            ink=True,
            on_click=lambda _e, target=color: pick_color(target),
            content=(
                ft.Icon(ft.Icons.CHECK, size=16, color=ft.Colors.WHITE)
                if color == init_color
                else None
            ),
        )
        swatches.append((color, container))
        return container

    color_row = ft.Row(
        spacing=6,
        run_spacing=6,
        wrap=True,
        controls=[make_swatch(color) for color in config.COLOR_PALETTE],
    )

    # ---- 周次多选 ----
    picker = WeekPicker(page, settings.total_weeks, init_weeks)

    body = ft.Column(
        spacing=10,
        scroll=ft.ScrollMode.AUTO,
        controls=[
            name_field,
            weekday_dropdown,
            ft.Row(
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[start_dropdown, ft.Text("至", size=13), end_dropdown],
            ),
            ft.Row(
                spacing=8,
                controls=[ft.Container(content=location_field, expand=True),
                          ft.Container(content=teacher_field, expand=True)],
            ),
            note_field,
            ft.Text("课程颜色", size=13, weight=ft.FontWeight.W_500),
            color_row,
            ft.Divider(height=1),
            ft.Text("上课周次", size=13, weight=ft.FontWeight.W_500),
            picker.control(),
            error_text,
        ],
    )

    # ---- 删除（仅编辑态）----
    def confirm_delete(_event: ft.ControlEvent) -> None:
        def do_delete(e: ft.ControlEvent) -> None:
            page.pop_dialog()  # 关掉确认框
            page.pop_dialog()  # 关掉表单
            state.delete_course(course.id)  # 触发落盘与两视图刷新

        confirm = ft.AlertDialog(
            modal=True,
            title=ft.Text("删除课程"),
            content=ft.Text(f"确定删除「{course.name}」吗？此操作无法撤销。"),
            actions=[
                ft.TextButton(content="取消", on_click=lambda _e: page.pop_dialog()),
                ft.Button(content="删除", bgcolor=ft.Colors.RED, color=ft.Colors.WHITE, on_click=do_delete),
            ],
        )
        page.show_dialog(confirm)

    # ---- 保存 ----
    def save(_event: ft.ControlEvent) -> None:
        clear_error()
        name = (name_field.value or "").strip()
        if not name:
            show_error("请填写课程名称")
            return

        weeks = picker.value()
        if not weeks:
            show_error("请至少选择一个上课周次")
            return

        result = Course(
            name=name,
            weekday=int(weekday_dropdown.value or "1"),
            start_slot=int(start_dropdown.value or "1"),
            end_slot=int(end_dropdown.value or "1"),
            weeks=weeks,
            location=(location_field.value or "").strip(),
            teacher=(teacher_field.value or "").strip(),
            note=(note_field.value or "").strip(),
            color=selected_color[0],
        )
        if is_edit:
            result.id = course.id
            state.update_course(result)
        else:
            state.add_course(result)

        page.pop_dialog()
        if on_saved:
            on_saved(result)

    actions = [ft.TextButton(content="取消", on_click=lambda _e: page.pop_dialog())]
    if is_edit:
        actions.insert(0, ft.TextButton(content="删除", on_click=confirm_delete))
    actions.append(
        ft.Button(content="保存", icon=ft.Icons.CHECK, on_click=save)
    )

    form_width, form_height = _form_size(page)

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("编辑课程" if is_edit else "新增课程"),
        content=ft.Container(width=form_width, height=form_height, content=body),
        actions=actions,
    )
    page.show_dialog(dialog)
