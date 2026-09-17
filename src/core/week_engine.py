"""周次引擎：日期与周次的互推、周次表达式解析、按周 / 按日过滤、课程块布局。

两条重要约定：
1. 周次从 1 开始计数；第 1 周即开学日期所在的那一周（周一为起点）。
2. 所有"越界"入口都做夹紧而不是抛异常 —— 用户把日期翻到学期外是很正常的操作，
   界面应该稳定停在最近的有效周，而不是崩溃。

本模块不依赖 flet，可以被测试脚本直接调用。
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from core.models import Course, SemesterSettings

# 允许用户写的各种分隔与连接符，统一归一化后再解析
_SEPARATORS = re.compile(r"[,，;；、\s]+")
# 连接符必须同时覆盖半角与全角：中文输入法下很容易打出 "1－16"（U+FF0D）或 "1～16"（U+FF5E）
_RANGE = re.compile(r"^(\d+)\s*[-–—－~～〜至到]\s*(\d+)$")
_SINGLE = re.compile(r"^(\d+)$")
_ALL_KEYWORDS = {"全", "全部", "所有", "all"}


# --------------------------------------------------------------------------- #
# 周次表达式解析与格式化
# --------------------------------------------------------------------------- #

def parse_weeks(text: str, max_weeks: int = 999) -> list[int]:
    """把 "1-16" / "1,3,5" / "1-16单" / "5双" / "全" 解析成排序去重的周次列表。

    无法识别的片段会被静默忽略（表单里会另外做"至少选一周"的校验），
    这样用户输错一部分不会导致整串失效。
    """
    if not text:
        return []

    found: set[int] = set()
    for raw_part in _SEPARATORS.split(text.strip()):
        part = raw_part.strip()
        if not part:
            continue

        # 先剥离单双周后缀
        parity: int | None = None
        if part.endswith("单"):
            parity = 1
            part = part[:-1].strip()
        elif part.endswith("双"):
            parity = 0
            part = part[:-1].strip()

        if part.lower() in _ALL_KEYWORDS:
            candidates = range(1, max_weeks + 1)
        else:
            range_match = _RANGE.match(part)
            single_match = _SINGLE.match(part)
            if range_match:
                low, high = int(range_match.group(1)), int(range_match.group(2))
                if low > high:
                    low, high = high, low
                # **先夹到 max_weeks 再展开**：手滑写成 "1-999999999" 时
                # range 会生成上亿个值，循环能把界面卡死（手机上就是 ANR）
                low = max(low, 1)
                high = min(high, max_weeks)
                candidates = range(low, high + 1) if low <= high else range(0)
            elif single_match:
                only = int(single_match.group(1))
                candidates = range(only, only + 1) if 1 <= only <= max_weeks else range(0)
            else:
                continue  # 认不出来就跳过这一段

        for week in candidates:
            if parity is not None and week % 2 != parity:
                continue
            if 1 <= week <= max_weeks:
                found.add(week)

    return sorted(found)


def compress_runs(weeks: list[int]) -> list[tuple[int, int]]:
    """把连续周次压成区间列表：[1,2,3,5] -> [(1,3),(5,5)]。"""
    if not weeks:
        return []
    ordered = sorted({w for w in weeks if w >= 1})
    runs: list[tuple[int, int]] = []
    start = previous = ordered[0]
    for week in ordered[1:]:
        if week == previous + 1:
            previous = week
            continue
        runs.append((start, previous))
        start = previous = week
    runs.append((start, previous))
    return runs


def format_weeks(weeks: list[int], max_inline: int = 6) -> str:
    """把周次列表压成紧凑文案，供列表与卡片显示。"""
    if not weeks:
        return "—"

    # 全部周次且长度像"整学期"时，直接说全周次更省地方
    pieces = []
    for low, high in compress_runs(weeks):
        pieces.append(f"{low}" if low == high else f"{low}-{high}")
        if len(pieces) >= max_inline:
            pieces.append("…")
            break
    return ",".join(pieces)


# --------------------------------------------------------------------------- #
# 日期 <-> 周次
# --------------------------------------------------------------------------- #

def clamp_week(week: int, total_weeks: int) -> int:
    """把周次夹到 1..total_weeks。"""
    if total_weeks < 1:
        total_weeks = 1
    return min(max(int(week), 1), total_weeks)


def semester_end(start: date, total_weeks: int) -> date:
    """学期最后一天的日期（第 total_weeks 周的周日）。"""
    return start + timedelta(days=max(1, total_weeks) * 7 - 1)


def clamp_to_semester(start: date, total_weeks: int, day: date) -> date:
    """把任意日期夹进学期区间；今天不在学期内时落到最近的学期边界。

    这正是"回到今天"按钮需要的行为。
    """
    if day < start:
        return start
    end = semester_end(start, total_weeks)
    if day > end:
        return end
    return day


def is_in_semester(start: date, total_weeks: int, day: date) -> bool:
    return start <= day <= semester_end(start, total_weeks)


def week_of_date(start: date, total_weeks: int, day: date) -> int:
    """日期落在第几周。学期之前算第 1 周，学期之后算最后一周。"""
    offset = (day - start).days
    if offset < 0:
        return 1
    return clamp_week(offset // 7 + 1, total_weeks)


def date_of_week_day(start: date, week: int, weekday: int) -> date:
    """第 week 周、星期 weekday（1=周一）对应的日期，不加夹紧。

    计算"整周的 7 个日期"时必须用这个不加夹紧的版本，
    否则学期首尾那一周会出现日期塌缩、两天指向同一天。
    """
    return start + timedelta(weeks=max(1, week) - 1, days=min(max(weekday, 1), 7) - 1)


def week_date_range(start: date, total_weeks: int, week: int) -> tuple[date, date]:
    """第 week 周的 (周一, 周日)。周次本身会先被夹紧。"""
    safe_week = clamp_week(week, total_weeks)
    return (
        date_of_week_day(start, safe_week, 1),
        date_of_week_day(start, safe_week, 7),
    )


def week_dates(start: date, week: int) -> list[date]:
    """第 week 周的 7 个日期，周一在前。"""
    return [date_of_week_day(start, week, weekday) for weekday in range(1, 8)]


def relative_week_label(start: date, total_weeks: int, week: int, today: date | None = None) -> str:
    """给周次加一个"本周 / 已过 / 未到"的提示，方便用户定位。"""
    today = today or date.today()
    current = week_of_date(start, total_weeks, today)
    if week < current:
        return "已过"
    if week == current:
        return "本周"
    return "未到"


# --------------------------------------------------------------------------- #
# 过滤
# --------------------------------------------------------------------------- #

def active_courses(courses: list[Course], week: int) -> list[Course]:
    """这一周实际要上的课（"非本周不显示"的唯一判定入口）。"""
    return [course for course in courses if course.is_active(week)]


def courses_on_date(courses: list[Course], weekday: int, week: int) -> list[Course]:
    """某一天的课。week 由调用方给出，避免两条视图各算一遍周次。"""
    return [
        course
        for course in courses
        if course.weekday == weekday and course.is_active(week)
    ]


def courses_of_week(courses: list[Course], week: int) -> dict[int, list[Course]]:
    """按星期分组的当周课程，键为 1..7。"""
    grouped: dict[int, list[Course]] = {weekday: [] for weekday in range(1, 8)}
    for course in active_courses(courses, week):
        grouped[course.weekday].append(course)
    return grouped


# --------------------------------------------------------------------------- #
# 课程块布局（周视图与单日视图共用）
# --------------------------------------------------------------------------- #

def layout_lanes(courses: list[Course]) -> list[dict]:
    """给同一天的课程分配横向"车道"，解决同一时段有多门课的情况。

    返回每门课附带 lane（第几车道，0 起）与 lane_count（它所在的重叠簇共几条车道）。
    lane_count 按簇计算，这样只在真正重叠时才分列，其余情况仍然是整格宽。
    """
    if not courses:
        return []

    # 先按起始节次排序，保证车道分配结果稳定
    ordered = sorted(courses, key=lambda c: (c.start_slot, c.end_slot, c.name))

    lanes: list[list[Course]] = []
    assigned: list[tuple[Course, int]] = []
    for course in ordered:
        lane = 0
        while True:
            if lane >= len(lanes):
                lanes.append([])
                break
            clash = any(
                not (course.end_slot < other.start_slot or course.start_slot > other.end_slot)
                for other in lanes[lane]
            )
            if not clash:
                break
            lane += 1
        lanes[lane].append(course)
        assigned.append((course, lane))

    blocks: list[dict] = []
    for course, lane in assigned:
        # 簇内车道数 = 所有与之直接重叠的课程里最大的 lane 序号 + 1
        overlapping_lanes = [
            other_lane
            for other, other_lane in assigned
            if other is course
            or not (course.end_slot < other.start_slot or course.start_slot > other.end_slot)
        ]
        lane_count = max(overlapping_lanes) + 1 if overlapping_lanes else lane + 1
        blocks.append(
            {
                "course": course,
                "lane": lane,
                "lane_count": lane_count,
                "start_slot": course.start_slot,
                "end_slot": course.end_slot,
                "span": course.span,
            }
        )
    return blocks


def blocks_for_date(courses: list[Course], settings: SemesterSettings, day: date) -> list[dict]:
    """某一天的课程块（含车道布局）。

    周视图与单日视图都调用这一个函数 —— 两边的显示结果因此不可能出现分歧。
    """
    week = week_of_date(settings.start_date_obj(), settings.total_weeks, day)
    same_day = courses_on_date(courses, day.isoweekday(), week)
    return layout_lanes(same_day)


def blocks_of_week(courses: list[Course], settings: SemesterSettings, week: int) -> dict[int, list[dict]]:
    """一整周的课程块，键为 1..7。周视图直接用它渲染 7 列。"""
    monday, _ = week_date_range(settings.start_date_obj(), settings.total_weeks, week)
    return {
        offset + 1: blocks_for_date(courses, settings, monday + timedelta(days=offset))
        for offset in range(7)
    }
