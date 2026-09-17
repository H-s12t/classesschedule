"""周视图与单日视图共用的布局工具与课程块渲染。

把宽度换算与课程块外观收敛到一处，是为了让两个视图在视觉与几何上保持一致：
只要块的高度公式变了，两个视图会同时变，不会出现一边高一边矮。
"""

from __future__ import annotations

import math
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


# 字号在真机试用后整体上调过一轮（各 +2）：原字号在手机上偏小
_NAME_SIZE_WIDE = 12
_NAME_SIZE_MEDIUM = 11
_NAME_SIZE_NARROW = 10
# 窄于这个宽度就连地点都放不下了，只留课名更干净
_NARROW_COLUMN = 42.0

# 课块内次要信息行的字号，以及字号→行高的换算系数。
# Flutter 默认行高约为字号的 1.3 倍，用来估算课块能放下几行。
_SECONDARY_SIZE = 12
_LINE_HEIGHT_RATIO = 1.3

# 块宽超过这个值，就把备注挪到右侧的空白列。
# 单日视图在大屏上块很宽（可到 500+ px），而课名+地点只占左边一小条，
# 备注挤在下面纯属浪费水平空间。低于此值时右侧列会被压得比正文还窄，
# 不如维持纵向堆叠（手机竖屏、周视图都走那条路）。
_SPLIT_MIN_WIDTH = 380.0


def _is_wide(ch: str) -> bool:
    """是否宽字形（中日韩）。窄字形按半宽算。"""
    code = ord(ch)
    return (
        0x1100 <= code <= 0x115F  # 韩文字母
        or 0x2E80 <= code <= 0xA4CF  # 部首、假名、汉字
        or 0xAC00 <= code <= 0xD7A3  # 韩文音节
        or 0xF900 <= code <= 0xFAFF  # 兼容汉字
        or 0xFF00 <= code <= 0xFF60  # 全角标点
    )


def estimated_lines(text: str, size: int, width: float) -> int:
    """估算一段文字在给定宽度下会占几行。

    Flutter 里中文字形宽≈字号、西文≈0.55 倍字号，照此粗算就够用：
    这里只是为了不把"课块能放几行"拍脑袋，不需要精确排版。
    """
    if not text or width <= 0:
        return 1
    units = sum(1.0 if _is_wide(ch) else 0.55 for ch in text)
    total = units * size
    if total <= width:
        return 1
    return max(1, math.ceil(total / width))


def _secondary_capacity(height: float, name_size: int, name_lines: int) -> int:
    """课名占 name_lines 行之后，这个高度里还能再放几行 12pt 的次要信息。"""
    remaining = max(height, 0.0) - name_size * _LINE_HEIGHT_RATIO * name_lines
    capacity = 0
    while remaining - _SECONDARY_SIZE * _LINE_HEIGHT_RATIO >= 0:
        remaining -= _SECONDARY_SIZE * _LINE_HEIGHT_RATIO
        capacity += 1
    return capacity


def _fit_notes(texts: list[str], room: int) -> list[str]:
    """备注放不下两条时先合并成一行（仍带标记区分），一条都放不下才丢弃。"""
    if not texts or len(texts) <= room:
        return texts
    return [" / ".join(texts)] if room >= 1 else []


def name_font_size(column_width: float, detailed: bool) -> int:
    """按可用宽度选择课名字号。

    手机竖屏下周视图每列只有 45px 左右，字号偏大会把课名截得只剩一两个字。
    """
    if detailed:
        return 14
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
    notes: tuple[str, str] = ("", ""),
    on_long_press: Callable[[Course], None] | None = None,
) -> ft.Container:
    """渲染一个课程块。

    detailed=True 用于单日视图（列宽大，可展示更多信息）。
    notes 是 (课程级备注, 单节课备注)，只有 detailed 时才显示。
    """
    course: Course = block["course"]
    geometry = block_geometry(block, column_width, row_height)
    name_size = name_font_size(column_width, detailed)

    # 课块高度是固定的（由节次决定），字号又大，所以**必须算出行数预算**：
    # 否则内容溢出容器，字会被直接裁掉，看起来像渲染坏了。
    text_width = max(geometry["width"] - 8.0, 0.0)  # 减去左右各 4px 内边距
    inner_height = max(geometry["height"] - 6.0, 0.0)  # 减去上下内边距
    name_lines = min(
        estimated_lines(course.name, name_size, text_width),
        3 if detailed else 4,
    )
    capacity = _secondary_capacity(inner_height, name_size, name_lines)

    name = ft.Text(
        course.name,
        size=name_size,
        weight=ft.FontWeight.W_500,
        color=ft.Colors.WHITE,
        max_lines=3 if detailed else 4,
        overflow=ft.TextOverflow.ELLIPSIS,
    )

    # 课名下面那一行：单日视图是「地点 · 教师」，周视图只有地点（列宽有限）
    head: list[ft.Control] = []
    if detailed:
        detail = course.summary()
        if detail:
            head.append(
                ft.Text(detail, size=_SECONDARY_SIZE, color="#EEF4FF", max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS)
            )
    elif course.location and shows_secondary_line(column_width, detailed):
        head.append(
            ft.Text(course.location, size=10, color="#EEF4FF", max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS)
        )

    # 节次范围排最后：课块自身的位置与高度已经表达了节次，挤不下时先丢它
    span_line: list[ft.Control] = []
    if detailed and course.span > 1:
        span_line.append(
            ft.Text(f"第{course.start_slot}-{course.end_slot}节",
                    size=_SECONDARY_SIZE, color="#DCE9FF")
        )

    note_texts: list[str] = []
    if detailed:
        course_note, session_note = notes
        if course_note:
            note_texts.append(f"{config.NOTE_MARK_COURSE} {course_note}")
        if session_note:
            note_texts.append(f"{config.NOTE_MARK_SESSION} {session_note}")

    def note_rows(texts: list[str]) -> list[ft.Control]:
        return [
            ft.Text(text, size=_SECONDARY_SIZE, color="#FFF3D6", max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS)
            for text in texts
        ]

    if note_texts and geometry["width"] >= _SPLIT_MIN_WIDTH:
        # 块够宽：备注挪进右侧那块本来就要空着的区域。
        # 好处不只是少留白 —— 备注不再和课名抢垂直空间，
        # 单节块（只有 60px 高）也能把两条备注分开显示，不必合并成一行。
        left = [name, *head, *span_line][: 1 + capacity]
        room = _secondary_capacity(inner_height, 0, 0)
        content: ft.Control = ft.Row(
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.START,
            controls=[
                ft.Container(expand=3, content=ft.Column(spacing=1, controls=left)),
                ft.Container(
                    expand=2,
                    content=ft.Column(
                        spacing=1, controls=note_rows(_fit_notes(note_texts, room))
                    ),
                ),
            ],
        )
    else:
        # 窄块：退回纵向堆叠。优先级 课名 → 摘要 → 备注 → 节次范围，
        # 放不下的从后往前丢（备注全文在弹层里始终可见）
        room_for_notes = max(0, capacity - len(head))
        stacked = [name, *head, *note_rows(_fit_notes(note_texts, room_for_notes)), *span_line]
        content = ft.Column(spacing=1, controls=stacked[: 1 + capacity])

    handler = (lambda _e: on_click(course)) if on_click else None
    long_handler = (lambda _e: on_long_press(course)) if on_long_press else None

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
        on_long_press=long_handler,
        content=content,
    )
