#!/usr/bin/env python3
"""核心层自测：不依赖 flet，可直接 python tools/selfcheck.py 运行。

覆盖计划中列出的验证项：
  1. 周次表达式解析（含单双周、乱输容错）
  2. 日期与周次互推、学期边界夹紧
  3. 按周过滤与按日过滤的**一致性交叉校验**（防止两条视图逻辑分叉）
  4. 同日重叠课程的横向车道分配
  5. 序列化往返
  6. 持久化原子写入往返

退出码非 0 表示有断言失败。
"""

from __future__ import annotations

import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

# 让脚本能直接导入 src 下的 core 包
SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

from core import storage, week_engine  # noqa: E402
from core.models import Course, ScheduleData, SemesterSettings  # noqa: E402

PASSED = 0
FAILED: list[str] = []


def check(label: str, actual: object, expected: object) -> None:
    global PASSED
    if actual == expected:
        PASSED += 1
    else:
        FAILED.append(f"{label}\n    实际: {actual!r}\n    期望: {expected!r}")


def check_true(label: str, value: object) -> None:
    check(label, bool(value), True)


# --------------------------------------------------------------------------- #
# 1. 周次表达式解析
# --------------------------------------------------------------------------- #

def test_parse_weeks() -> None:
    check("1-16 区间", week_engine.parse_weeks("1-16"), list(range(1, 17)))
    check("逗号分隔", week_engine.parse_weeks("1,3,5"), [1, 3, 5])
    check("中文逗号", week_engine.parse_weeks("1，3，5"), [1, 3, 5])
    check("1-16 单周", week_engine.parse_weeks("1-16单"), [1, 3, 5, 7, 9, 11, 13, 15])
    check("1-16 双周", week_engine.parse_weeks("1-16双"), [2, 4, 6, 8, 10, 12, 14, 16])
    check("单周但起始为偶数", week_engine.parse_weeks("4-10单"), [5, 7, 9])
    check("单节带单双周", week_engine.parse_weeks("5单"), [5])
    check("单节带双周且不匹配", week_engine.parse_weeks("5双"), [])
    check("全周次", week_engine.parse_weeks("全", max_weeks=4), [1, 2, 3, 4])
    check("混合写法", week_engine.parse_weeks("1-3, 6, 9-10"), [1, 2, 3, 6, 9, 10])
    check("倒序区间自动纠正", week_engine.parse_weeks("8-5"), [5, 6, 7, 8])
    check("去重并排序", week_engine.parse_weeks("3,1,3,2"), [1, 2, 3])
    check("超范围被剔除", week_engine.parse_weeks("1-30", max_weeks=20), list(range(1, 21)))
    check("乱输不炸且部分容错", week_engine.parse_weeks("abc,7,###"), [7])
    check("空串", week_engine.parse_weeks(""), [])
    check("全角区间符", week_engine.parse_weeks("1－4"), [1, 2, 3, 4])

    check("格式化连续区间", week_engine.format_weeks([1, 2, 3, 5, 6]), "1-3,5-6")
    check("格式化空列表", week_engine.format_weeks([]), "—")


# --------------------------------------------------------------------------- #
# 2. 日期与周次互推、边界夹紧
# --------------------------------------------------------------------------- #

def test_week_math() -> None:
    # 2026-09-07 是周一
    start = date(2026, 9, 7)
    total = 20

    check("开学当天是第 1 周", week_engine.week_of_date(start, total, date(2026, 9, 7)), 1)
    check("第 1 周周日仍是第 1 周", week_engine.week_of_date(start, total, date(2026, 9, 13)), 1)
    check("第 2 周周一", week_engine.week_of_date(start, total, date(2026, 9, 14)), 2)
    check("开学前算第 1 周", week_engine.week_of_date(start, total, date(2026, 8, 1)), 1)
    check(
        "超出总周数夹到最后一周",
        week_engine.week_of_date(start, total, date(2027, 5, 1)),
        20,
    )

    check("第 3 周周一的日期", week_engine.date_of_week_day(start, 3, 1), date(2026, 9, 21))
    check("第 3 周周日的日期", week_engine.date_of_week_day(start, 3, 7), date(2026, 9, 27))
    check("整周日期不塌缩", len(set(week_engine.week_dates(start, 1))), 7)

    check(
        "周日期范围",
        week_engine.week_date_range(start, total, 2),
        (date(2026, 9, 14), date(2026, 9, 20)),
    )
    check("越界周次被夹紧", week_engine.week_date_range(start, total, 99)[0], date(2027, 1, 18))

    check("学期内日期不移动", week_engine.clamp_to_semester(start, total, date(2026, 9, 10)), date(2026, 9, 10))
    check("早于开学落到开学日", week_engine.clamp_to_semester(start, total, date(2020, 1, 1)), start)
    check(
        "晚于期末落到期末",
        week_engine.clamp_to_semester(start, total, date(2030, 1, 1)),
        date(2026, 9, 7) + timedelta(days=20 * 7 - 1),
    )
    check_true("学期末判定", week_engine.is_in_semester(start, total, date(2026, 9, 7) + timedelta(days=139)))
    check("期末次日不在学期内", week_engine.is_in_semester(start, total, date(2026, 9, 7) + timedelta(days=140)), False)


# --------------------------------------------------------------------------- #
# 3. 按周与按日过滤的一致性交叉校验
# --------------------------------------------------------------------------- #

def build_sample() -> ScheduleData:
    """构造一份包含各种边界情况的样本数据。"""
    data = ScheduleData(
        settings=SemesterSettings(total_weeks=20, start_date="2026-09-07", slots_per_day=12),
        courses=[
            # 仅第 5-8 周、周三第 3-4 节（计划里的核心验证用例）
            Course(name="数据结构", weekday=3, start_slot=3, end_slot=4,
                   weeks=[5, 6, 7, 8], location="A101", teacher="张老师"),
            # 贯穿全学期的周一第 1 节
            Course(name="英语", weekday=1, start_slot=1, end_slot=2,
                   weeks=list(range(1, 21)), location="B203"),
            # 只在单周的周五第 9 节
            Course(name="体育", weekday=5, start_slot=9, end_slot=9,
                   weeks=[1, 3, 5, 7, 9], location="操场"),
            # 与下一门课完全重叠，用于车道分配
            Course(name="选修A", weekday=2, start_slot=5, end_slot=6, weeks=[1, 2, 3]),
            Course(name="选修B", weekday=2, start_slot=5, end_slot=6, weeks=[1, 2, 3]),
            # 部分重叠
            Course(name="选修C", weekday=2, start_slot=6, end_slot=8, weeks=[1, 2, 3]),
            # 第 20 周（最后一周）的边界课程
            Course(name="结课讲座", weekday=7, start_slot=12, end_slot=12, weeks=[20]),
        ],
    )
    data.normalize()
    return data


def test_week_day_consistency(data: ScheduleData) -> None:
    """遍历学期内每一天，断言"按周分组"和"按日过滤"给出同一结果。

    这是防止两条视图逻辑分叉最直接的手段 —— 只要这个不变量成立，
    周视图与单日视图就不可能出现"某天有课但另一处不显示"的矛盾。
    """
    settings = data.settings
    start = settings.start_date_obj()
    total = settings.total_weeks

    for offset in range(total * 7):
        day = start + timedelta(days=offset)
        week = week_engine.week_of_date(start, total, day)

        by_week = week_engine.courses_of_week(data.courses, week).get(day.isoweekday(), [])
        by_day = week_engine.courses_on_date(data.courses, day.isoweekday(), week)

        names_week = sorted(course.name for course in by_week)
        names_day = sorted(course.name for course in by_day)
        if names_week != names_day:
            FAILED.append(
                f"一致性交叉校验失败 @ {day}（第 {week} 周 星期{day.isoweekday()}）\n"
                f"    按周分组: {names_week}\n    按日过滤: {names_day}"
            )
            return

        # 课程块布局也必须一致
        week_blocks = [b["course"].name for b in week_engine.blocks_for_date(data.courses, settings, day)]
        day_blocks = [b["course"].name for b in week_engine.blocks_for_date(data.courses, settings, day)]
        if sorted(week_blocks) != sorted(day_blocks):
            FAILED.append(f"课程块布局不一致 @ {day}")
            return

    global PASSED
    PASSED += 1


def test_week_filtering(data: ScheduleData) -> None:
    """"非本周不显示"的核心断言。"""
    settings = data.settings

    def names_on(day: date) -> list[str]:
        return sorted(b["course"].name for b in week_engine.blocks_for_date(data.courses, settings, day))

    # 第 5 周的周三（开学 9/7 是周一，第 5 周周一 = 9/7 + 28 天 = 10/5，周三 = 10/7）
    # 注意：英语是周一（weekday=1）的课，周三不应出现
    check("第 5 周周三有数据结构", names_on(date(2026, 10, 7)), ["数据结构"])
    # 第 3 周的周三：数学课尚未开始
    check("第 3 周周三无数据结构", "数据结构" in names_on(date(2026, 9, 23)), False)
    # 第 9 周（不在 5-8 内）同样不应出现
    check("第 9 周周三无数据结构", "数据结构" in names_on(date(2026, 11, 4)), False)
    # 第 8 周仍应出现
    check("第 8 周周三仍有数据结构", "数据结构" in names_on(date(2026, 10, 28)), True)
    # 单周课：第 1 周周五有体育，第 2 周周五没有
    check("第 1 周周五有体育", "体育" in names_on(date(2026, 9, 11)), True)
    check("第 2 周周五无体育", "体育" in names_on(date(2026, 9, 18)), False)
    # 最后一周的边界课程
    check("第 20 周周日有结课讲座", "结课讲座" in names_on(date(2027, 1, 24)), True)


# --------------------------------------------------------------------------- #
# 4. 车道分配
# --------------------------------------------------------------------------- #

def test_lane_layout(data: ScheduleData) -> None:
    # 第 1 周周二：选修A / 选修B 完全重叠，选修C 与之部分重叠 → 三条车道
    tuesday = date(2026, 9, 8)
    blocks = week_engine.blocks_for_date(data.courses, data.settings, tuesday)
    by_name = {b["course"].name: b for b in blocks}

    check("重叠场景有 3 门课", len(blocks), 3)
    check("选修A 车道", by_name["选修A"]["lane"], 0)
    check("选修B 车道", by_name["选修B"]["lane"], 1)
    check("选修A 车道数", by_name["选修A"]["lane_count"], 3)
    check("选修C 车道数", by_name["选修C"]["lane_count"], 3)

    # 不重叠时应当是整格宽（lane_count == 1）
    monday = date(2026, 9, 7)
    monday_blocks = week_engine.blocks_for_date(data.courses, data.settings, monday)
    check("不重叠时 lane_count 为 1", [b["lane_count"] for b in monday_blocks], [1])

    # 跨节次课程的跨度
    wednesday = date(2026, 10, 7)
    wed_blocks = {b["course"].name: b for b in week_engine.blocks_for_date(data.courses, data.settings, wednesday)}
    check("数据结构跨度 2 节", wed_blocks["数据结构"]["span"], 2)
    check("数据结构起止", (wed_blocks["数据结构"]["start_slot"], wed_blocks["数据结构"]["end_slot"]), (3, 4))


# --------------------------------------------------------------------------- #
# 5. 序列化往返
# --------------------------------------------------------------------------- #

def test_serialization(data: ScheduleData) -> None:
    restored = ScheduleData.from_dict(data.to_dict())
    check("往返后课程数一致", len(restored.courses), len(data.courses))
    check("往返后设置一致", restored.settings.to_dict(), data.settings.to_dict())
    check(
        "往返后课程字段一致",
        [c.to_dict() for c in restored.courses],
        [c.to_dict() for c in data.courses],
    )
    # 二次往返必须稳定（幂等）
    check("二次往返稳定", ScheduleData.from_dict(restored.to_dict()).to_dict(), data.to_dict())

    # 脏数据容错
    dirty = ScheduleData.from_dict(
        {
            "settings": {"total_weeks": "abc", "slots_per_day": 999, "slot_times": None},
            "courses": [{"name": None, "weekday": 99, "start_slot": -3, "end_slot": 99, "weeks": [3, 1, 1, -2, "x"]}],
        }
    )
    check("脏数据总周数兜底", dirty.settings.total_weeks, 20)
    check("脏数据节数夹紧", dirty.settings.slots_per_day, 16)
    check("脏数据 slot_times 补全", len(dirty.settings.slot_times), 16)
    check("脏数据星期夹紧", dirty.courses[0].weekday, 7)
    check("脏数据起止节次夹紧", (dirty.courses[0].start_slot, dirty.courses[0].end_slot), (1, 16))
    check("脏数据周次清洗", dirty.courses[0].weeks, [1, 3])
    check("空名字兜底", dirty.courses[0].name, "未命名课程")


# --------------------------------------------------------------------------- #
# 6. 持久化往返
# --------------------------------------------------------------------------- #

def test_storage(data: ScheduleData) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        storage.set_data_dir(tmp)

        storage.save(data)
        check_true("数据文件已生成", storage.data_file().exists())
        check("无临时文件残留", sorted(p.name for p in Path(tmp).iterdir()), ["schedule.json"])

        reloaded = storage.load()
        check("重新载入课程数一致", len(reloaded.courses), len(data.courses))
        check("重新载入内容一致", reloaded.to_dict(), data.to_dict())

        # 文件损坏时应留档并返回默认数据，而不是抛异常
        storage.data_file().write_text("{ 这不是合法 JSON", encoding="utf-8")
        salvaged = storage.load()
        check("损坏文件后返回空数据", len(salvaged.courses), 0)
        leftovers = sorted(p.name for p in Path(tmp).iterdir())
        check_true("损坏文件被改名留档", any(name.endswith(".corrupt") for name in leftovers))

    storage.set_data_dir(None)


# --------------------------------------------------------------------------- #

def main() -> int:
    test_parse_weeks()
    test_week_math()

    data = build_sample()
    test_week_day_consistency(data)
    test_week_filtering(data)
    test_lane_layout(data)
    test_serialization(data)
    test_storage(data)

    print(f"通过 {PASSED} 项")
    if FAILED:
        print(f"失败 {len(FAILED)} 项：\n")
        for item in FAILED:
            print(f"  ✗ {item}")
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
