"""周视图与单日视图共用的布局工具与课程块渲染。

把宽度换算与课程块外观收敛到一处，是为了让两个视图在视觉与几何上保持一致：
只要块的高度公式变了，两个视图会同时变，不会出现一边高一边矮。
"""

from __future__ import annotations

from collections.abc import Callable

import flet as ft

from core import config
from core.models import Course

# 背景配色
# 交替色必须与纯白有明显对比，否则 12 行在浅色背景上分不出边界；
# 再加上显式的分隔线，才能在手机小屏上读清"第几节在哪一行"。
HEADER_BG = "#DCE7F5"
CELL_BG = "#FFFFFF"
CELL_ALT_BG = "#EFF5FB"
WEEKEND_BG = "#E3EBF6"
GRID_LINE = "#CFDCEA"
TODAY_HEADER_BG = "#1E88E5"
TEXT_ON_HEADER = "#37474F"


def horizontal_separators(row_height: float, slots: int, width: float) -> list[ft.Control]:
    """每节底部的分隔线，让行边界在任何底色上都清晰。"""
    return [
        ft.Container(
            left=0,
            top=slot * row_height - 1,
            width=width,
            height=1,
            bgcolor=GRID_LINE,
        )
        for slot in range(1, slots + 1)
    ]


def vertical_separator(column_width: float, total_height: float) -> ft.Control:
    """列右侧的竖线，用来分开星期或分开时间列与课程区。"""
    return ft.Container(
        left=max(column_width - 1, 0),
        top=0,
        width=1,
        height=total_height,
        bgcolor=GRID_LINE,
    )


def input_border() -> ft.OutlineInputBorder:
    """输入框统一圆角边框。

    Flet 1.0 起 TextField.border_radius 已废弃，正确写法是 border=OutlineInputBorder(...)。
    """
    return ft.OutlineInputBorder(border_radius=ft.BorderRadius.all(8))


def is_on_page(control: ft.Control | None) -> bool:
    """判断控件是否已经挂载到页面。

    **不要用 `control.page is None` 来探测**：Flet 1.0 的 `Control.page`
    会沿 parent 链向上找 Page，找不到就抛 RuntimeError，而不是返回 None。
    而 `Control.parent` 始终安全返回 None，所以这里自己沿链查找。
    """
    node = control
    while node is not None:
        if isinstance(node, ft.Page):
            return True
        node = node.parent
    return False


def page_width(page: ft.Page) -> float:
    """页面宽度。首帧布局完成前可能为 0，用兜底值避免算出负数列宽。"""
    try:
        value = float(getattr(page, "width", 0) or 0)
    except (TypeError, ValueError):
        value = 0.0
    return value if value > 1 else config.FALLBACK_PAGE_WIDTH


def content_width(page: ft.Page) -> float:
    """内容区可用宽度（已扣掉页面左右留白）。"""
    # 预留 8px 给滚动条与圆角，避免最右一列被裁掉
    return max(page_width(page) - config.CONTENT_PADDING * 2 - 8, 120.0)


def slot_background(slot: int, is_weekend: bool) -> str:
    """课节行底色：周末单独一色，平日隔行交替，便于横向读数。"""
    if is_weekend:
        return WEEKEND_BG
    return CELL_ALT_BG if slot % 2 == 0 else CELL_BG


def block_geometry(block: dict, column_width: float, row_height: float) -> dict:
    """把课程块换算成绝对定位所需的 left / top / width / height。

    这是两个视图唯一的几何来源：跨节次课程只改变 span，不改变公式。
    同一时段有多门课时按车道横向切分，否则占满整列。
    """
    span = max(1, int(block["span"]))
    lane_count = max(1, int(block["lane_count"]))
    lane = max(0, int(block["lane"]))

    if lane_count <= 1:
        left = 0.0
        width = column_width - config.BLOCK_GAP
    else:
        lane_width = column_width / lane_count
        left = lane * lane_width
        width = max(lane_width - config.BLOCK_GAP, 8.0)

    return {
        "left": left,
        "top": (int(block["start_slot"]) - 1) * row_height + 1,
        "width": max(width, 8.0),
        "height": span * row_height - config.BLOCK_GAP,
    }


_NAME_SIZE_WIDE = 10
_NAME_SIZE_MEDIUM = 9
_NAME_SIZE_NARROW = 8
# 窄于这个宽度就连地点都放不下了，只留课名更干净
_NARROW_COLUMN = 42.0


def name_font_size(column_width: float, detailed: bool) -> int:
    """按可用宽度选择课名字号。

    手机竖屏下周视图每列只有 45px 左右，字号偏大会把课名截得只剩一两个字。
    """
    if detailed:
        return 12
    if column_width >= 56:
        return _NAME_SIZE_WIDE
    if column_width >= _NARROW_COLUMN:
        return _NAME_SIZE_MEDIUM
    return _NAME_SIZE_NARROW


def shows_secondary_line(column_width: float, detailed: bool) -> bool:
    """是否还塞得下第二行信息（周视图是地点，单日视图是详情）。"""
    return True if detailed else column_width >= _NARROW_COLUMN


def course_block(
    block: dict,
    column_width: float,
    row_height: float,
    on_click: Callable[[Course], None] | None = None,
    detailed: bool = False,
) -> ft.Container:
    """渲染一个课程块。detailed=True 用于单日视图（列宽大，可展示更多信息）。"""
    course: Course = block["course"]
    geometry = block_geometry(block, column_width, row_height)

    lines: list[ft.Control] = [
        ft.Text(
            course.name,
            size=name_font_size(column_width, detailed),
            weight=ft.FontWeight.W_500,
            color=ft.Colors.WHITE,
            max_lines=3 if detailed else 4,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
    ]

    if detailed:
        # 单日视图列宽充足，把节次范围、地点、教师都摊开显示
        detail = course.summary()
        if detail:
            lines.append(
                ft.Text(detail, size=10, color="#EEF4FF", max_lines=2,
                        overflow=ft.TextOverflow.ELLIPSIS)
            )
        if course.span > 1:
            lines.append(
                ft.Text(f"第{course.start_slot}-{course.end_slot}节", size=10, color="#DCE9FF")
            )
    elif course.location and shows_secondary_line(column_width, detailed):
        # 周视图列宽有限，只补充地点；其余信息交给单日视图
        lines.append(
            ft.Text(course.location, size=8, color="#EEF4FF", max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS)
        )

    handler = (lambda _e: on_click(course)) if on_click else None

    return ft.Container(
        left=geometry["left"],
        top=geometry["top"],
        width=geometry["width"],
        height=geometry["height"],
        bgcolor=course.color,
        border_radius=ft.BorderRadius.all(5),
        padding=ft.Padding.symmetric(horizontal=4, vertical=3),
        ink=bool(on_click),
        on_click=handler,
        content=ft.Column(spacing=1, controls=lines),
    )
