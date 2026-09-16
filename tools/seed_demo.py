#!/usr/bin/env python3
"""生成一份演示数据，用于在 PC 上验证渲染效果。

写入位置必须与应用实际读取的位置一致，否则会出现"脚本写了数据但界面里没有课"。
应用在开发态的数据目录来自 Flet 注入的 FLET_APP_STORAGE_DATA
（形如 <app_path>/.flet/storage/data）；shell 里跑脚本时没有该环境变量，
因此这里显式对齐到同一位置（见 core.storage.use_dev_dir）。

用法：
    python tools/seed_demo.py             # 写入应用实际读取的开发数据目录
    python tools/seed_demo.py --dir /tmp/x
    python tools/seed_demo.py --show      # 只打印路径，不写入

演示数据刻意覆盖了这些渲染场景：
    - 跨节次课程（一节课占多行）
    - 同一时段两门课（横向分车道）
    - 单双周课程
    - 只在某一周出现的课
    - 最后一周的边界课程
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

from core import storage  # noqa: E402
from core.models import Course, ScheduleData, SemesterSettings  # noqa: E402

PALETTE = (
    "#4C8DFF", "#FF7A59", "#2EC4B6", "#F5A623", "#8E7CFF", "#E85D9A",
)


def build() -> ScheduleData:
    # 开学日取"本周一"，这样打开就是第 1 周且今天高亮可见
    today = date.today()
    monday = today - timedelta(days=today.isoweekday() - 1)

    data = ScheduleData(
        settings=SemesterSettings(
            total_weeks=20,
            start_date=monday.isoformat(),
            slots_per_day=12,
        ),
        courses=[
            Course(name="高等数学", weekday=1, start_slot=1, end_slot=2,
                   weeks=list(range(1, 19)), location="教一 101", teacher="王老师",
                   color=PALETTE[0]),
            Course(name="大学英语", weekday=3, start_slot=3, end_slot=4,
                   weeks=list(range(1, 21)), location="外语楼 205", teacher="李老师",
                   color=PALETTE[1]),
            Course(name="数据结构", weekday=2, start_slot=5, end_slot=6,
                   weeks=[5, 6, 7, 8, 9, 10, 11, 12], location="计算机楼 302",
                   teacher="张老师", color=PALETTE[2]),
            Course(name="线性代数", weekday=4, start_slot=5, end_slot=6,
                   weeks=list(range(1, 19)), location="教二 208", teacher="赵老师",
                   color=PALETTE[3]),
            # 与上一门完全重叠，用来验证横向车道
            Course(name="概率论", weekday=4, start_slot=5, end_slot=6,
                   weeks=[3, 4, 5, 6], location="教二 310", color=PALETTE[4]),
            Course(name="体育", weekday=5, start_slot=9, end_slot=10,
                   weeks=[1, 3, 5, 7, 9, 11], location="体育馆",
                   color=PALETTE[5]),
            Course(name="物理实验", weekday=2, start_slot=9, end_slot=11,
                   weeks=list(range(2, 18, 2)), location="实验楼 B1", teacher="孙老师",
                   color=PALETTE[1]),
            Course(name="结课讲座", weekday=7, start_slot=1, end_slot=2,
                   weeks=[20], location="报告厅", color=PALETTE[3]),
        ],
    )
    data.normalize()
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default=None,
                        help="指定的数据目录；不传则对齐到应用开发态实际使用的目录")
    parser.add_argument("--show", action="store_true", help="只打印数据文件路径，不写入")
    args = parser.parse_args()

    if args.dir:
        storage.set_data_dir(args.dir)
    else:
        storage.use_dev_dir()

    if args.show:
        print(f"应用数据文件: {storage.data_file()}")
        return 0

    storage.save(build())
    print(f"演示数据已写入: {storage.data_file()}")
    print("（重新加载应用页面即可看到课程块）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
