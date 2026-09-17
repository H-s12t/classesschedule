#!/usr/bin/env python3
"""视图构造自检：不需要浏览器，直接检查控件树是否符合预期。

Flet 的控件本质是数据类，构造视图并不需要真实会话，因此可以在这里
断言"课程块到底有没有被放进控件树、几何值是否合理"，
把渲染问题与逻辑问题分开定位。
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

import flet as ft  # noqa: E402

from seed_demo import build  # noqa: E402  同目录脚本，提供确定性的样本数据
from state import AppState  # noqa: E402
from ui.day_view import build_day_view  # noqa: E402
from ui.settings_view import build_settings_view  # noqa: E402
from ui import schedule_view  # noqa: E402


class FakePage:
    """只需要提供 width，其余接口视图层并不使用。"""

    def __init__(self, width: float = 412.0) -> None:
        self.width = width


def walk(control: object, depth: int = 0):
    """深度优先遍历控件树，产出 (depth, control)。"""
    yield depth, control
    for attr in ("controls", "content"):
        value = getattr(control, attr, None)
        if isinstance(value, list):
            for child in value:
                yield from walk(child, depth + 1)
        elif value is not None and hasattr(value, "controls") is not None:
            if hasattr(value, "__class__") and not isinstance(value, (str, int, float)):
                yield from walk(value, depth + 1)


def count_colored_blocks(root: object, colors: set[str]) -> list[tuple]:
    """找出所有底色等于课程颜色的容器，即课程块。"""
    found = []
    for _depth, control in walk(root):
        color = getattr(control, "bgcolor", None)
        if isinstance(color, str) and color.upper() in colors:
            found.append(
                (
                    color,
                    getattr(control, "left", None),
                    getattr(control, "top", None),
                    getattr(control, "width", None),
                    getattr(control, "height", None),
                )
            )
    return found


def find_labels(root: object) -> list[str]:
    """收集所有文本内容，用来确认关键控件确实在树里。"""
    labels = []
    for _depth, control in walk(root):
        value = getattr(control, "value", None)
        if isinstance(control, ft.Text) and isinstance(value, str):
            labels.append(value)
        content = getattr(control, "content", None)
        if isinstance(control, ft.Button) and isinstance(content, str):
            labels.append(content)
    return labels


def count_long_pressable(root: object, colors: set[str]) -> int:
    """统计同时接了长按回调的课程块数量（单日视图靠长按进课程编辑）。"""
    total = 0
    for _depth, control in walk(root):
        color = getattr(control, "bgcolor", None)
        if isinstance(color, str) and color.upper() in colors:
            if callable(getattr(control, "on_long_press", None)):
                total += 1
    return total


def count_split_blocks(root: object, colors: set[str]) -> int:
    """统计用了「左侧信息 / 右侧备注」两列布局的课程块数量。"""
    total = 0
    for _depth, control in walk(root):
        color = getattr(control, "bgcolor", None)
        if isinstance(color, str) and color.upper() in colors:
            if isinstance(getattr(control, "content", None), ft.Row):
                total += 1
    return total


def main() -> int:
    # 刻意使用内存中的固定样本，完全不读磁盘数据文件。
    # 校验器必须自带数据，否则会因"开发数据是否存在"给出误导性的成败结果
    # —— 之前就出现过无数据时退出码 1、被误读成校验失败的情况。
    state = AppState()
    state.data = build()

    page = FakePage(412.0)
    colors = {c.color.upper() for c in state.courses}

    print(f"课程数 {len(state.courses)}，页面宽度 {page.width}，当前周 {state.current_week}")

    problems: list[str] = []

    # ---- 周视图 ----
    week_view = schedule_view.build_schedule_view(
        page, state, on_pick_day=lambda d: None, on_edit_course=lambda c: None
    )
    week_blocks = count_colored_blocks(week_view, colors)
    expected = sum(len(b) for b in state.blocks_of_week(state.current_week).values())
    print(f"\n周视图：期望课程块 {expected} 个，实际找到 {len(week_blocks)} 个")
    for item in week_blocks:
        print(f"  色 {item[0]} left={item[1]} top={item[2]} w={item[3]} h={item[4]}")
    if len(week_blocks) != expected:
        problems.append(f"周视图课程块数量不符：期望 {expected}，实际 {len(week_blocks)}")

    # 几何值合理性
    for _color, left, top, width, height in week_blocks:
        if width is None or height is None or left is None or top is None:
            problems.append("课程块存在未设置的几何属性")
        elif width <= 0 or height <= 0:
            problems.append(f"课程块尺寸非法: w={width} h={height}")
        elif top < 0:
            problems.append(f"课程块 top 为负: {top}")

    # ---- 单日视图 ----
    state.select_date(state.selected_date)
    day_view = build_day_view(
        page,
        state,
        on_add_at=lambda d, s: None,
        on_edit_course=lambda c: None,
        on_edit_note=lambda d, c: None,
    )
    day_blocks = count_colored_blocks(day_view, colors)
    expected_day = len(state.blocks_for(state.selected_date))
    print(f"\n单日视图：期望课程块 {expected_day} 个，实际找到 {len(day_blocks)} 个")
    for item in day_blocks:
        print(f"  色 {item[0]} left={item[1]} top={item[2]} w={item[3]} h={item[4]}")
    if len(day_blocks) != expected_day:
        problems.append(f"单日视图课程块数量不符：期望 {expected_day}，实际 {len(day_blocks)}")

    # 单日视图必须能看到每节起止时间
    day_labels = find_labels(day_view)
    if "08:00 08:45" not in day_labels:
        problems.append("单日视图缺少节次时间显示")

    # ---- 备注：课程级与单节备注必须同时出现在课程块里 ----
    # 直接改内存数据、不走 persist()，免得校验器往开发数据文件里写脏数据
    first_id = state.blocks_for(state.selected_date)[0]["course"].id
    target = next(c for c in state.data.courses if c.id == first_id)
    target.note = "CHECK课程备注"
    state.data.set_session_note(state.selected_date, first_id, "CHECK单节备注")

    day_view = build_day_view(
        page,
        state,
        on_add_at=lambda d, s: None,
        on_edit_course=lambda c: None,
        on_edit_note=lambda d, c: None,
    )
    day_labels = find_labels(day_view)
    print(f"\n备注：带标记的文案 {[t for t in day_labels if 'CHECK' in t]}")
    for needed in ("CHECK课程备注", "CHECK单节备注"):
        if not any(needed in label for label in day_labels):
            problems.append(f"单日视图课程块缺少备注文案：{needed}")

    long_pressable = count_long_pressable(day_view, colors)
    print(f"  接入长按的课程块 {long_pressable}/{len(day_blocks)}")
    if long_pressable != len(day_blocks):
        problems.append("单日视图存在未接长按的课程块（无法从课块进课程编辑）")

    # ---- 宽屏：备注应该挪进块内右侧那块本来就要空着的区域 ----
    wide_view = build_day_view(
        FakePage(760.0),
        state,
        on_add_at=lambda d, s: None,
        on_edit_course=lambda c: None,
        on_edit_note=lambda d, c: None,
    )
    wide_blocks = len(count_colored_blocks(wide_view, colors))
    wide_split = count_split_blocks(wide_view, colors)
    print(f"\n宽屏 760：课程块 {wide_blocks} 个，其中用两列布局的 {wide_split} 个")
    if wide_blocks and wide_split != wide_blocks:
        problems.append(f"宽屏下仍有课块把备注堆在课名下面（{wide_split}/{wide_blocks}）")

    # ---- 设置视图 ----
    settings_view = build_settings_view(page, state)
    settings_labels = find_labels(settings_view)
    for needed in ("保存设置", "恢复默认时间", "各节起止时间"):
        if needed not in settings_labels:
            problems.append(f"设置视图缺少控件：{needed}")
    print(f"\n设置视图：收集到 {len(settings_labels)} 个文案")
    print("  结尾几个文案:", settings_labels[-5:] if settings_labels else "无")

    print()
    if problems:
        print(f"发现 {len(problems)} 个问题：")
        for item in problems:
            print(f"  ✗ {item}")
        return 1
    print("视图构造自检通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
