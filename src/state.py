"""跨视图共享状态。

设计要点：`selected_date` 是**唯一真相源**，`current_week` 由它实时推导。
于是"周视图翻页"就是日期 ±7 天、"单日视图翻页"就是日期 ±1 天、
"点周视图某天列"就是直接赋值为该日 —— 所有导航都只改一个字段，
两个视图在结构上不可能不同步，无需任何双向同步代码。

本模块不导入 flet，便于纯逻辑测试。
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta

from core import storage, week_engine
from core.models import Course, ScheduleData, SemesterSettings


class AppState:
    def __init__(self) -> None:
        self.data = ScheduleData()
        self.selected_date: date = date.today()
        self._listeners: list[Callable[[], None]] = []
        # 一次性提示文案：由界面在下次刷新建构时取走并显示
        self._flash: str | None = None

    # ------------------------------------------------------------------ #
    # 订阅与广播
    # ------------------------------------------------------------------ #

    def subscribe(self, listener: Callable[[], None]) -> None:
        """注册"状态变了请重绘"的回调（由界面层注册）。"""
        if listener not in self._listeners:
            self._listeners.append(listener)

    def notify(self) -> None:
        for listener in list(self._listeners):
            listener()

    # ------------------------------------------------------------------ #
    # 生命周期
    # ------------------------------------------------------------------ #

    def load(self) -> None:
        """从磁盘装载数据，并把选中日期夹进学期范围。"""
        self.data = storage.load()
        self.clamp_selected()

    def persist(self) -> bool:
        """落盘并广播；返回是否成功写入磁盘。

        每次数据变更都必须调用它 —— 打包后的应用退出时不做清理，
        没有"退出时统一保存"这种机会。

        保存失败必须让用户看见：数据只在内存里、用户以为存住了其实没有，
        是这类工具最糟糕的失败方式。因此失败时经一次性提示条明确告知。
        """
        try:
            storage.save(self.data)
        except OSError as exc:
            self._flash = f"保存失败，改动未写入磁盘：{exc}"
            self.notify()
            return False
        self.selected_date = self.clamp_selected()
        self.notify()
        return True

    def refresh(self) -> None:
        """只广播不落盘，用于视图切换、窗口尺寸变化这类纯界面刷新。"""
        self.notify()

    def set_flash(self, message: str) -> None:
        """设置一次性提示。会在下一次界面重建时被取走显示。"""
        self._flash = message
        self.notify()

    def take_flash(self) -> str | None:
        message, self._flash = self._flash, None
        return message

    # ------------------------------------------------------------------ #
    # 派生数据
    # ------------------------------------------------------------------ #

    @property
    def settings(self) -> SemesterSettings:
        return self.data.settings

    @property
    def courses(self) -> list[Course]:
        return self.data.courses

    @property
    def start_date(self) -> date:
        return self.settings.start_date_obj()

    @property
    def current_week(self) -> int:
        """选中日期落在第几周。所有"现在是第几周"的判断都走这里。"""
        return self.week_of(self.selected_date)

    def week_of(self, day: date) -> int:
        return week_engine.week_of_date(self.start_date, self.settings.total_weeks, day)

    def is_in_semester(self, day: date) -> bool:
        return week_engine.is_in_semester(self.start_date, self.settings.total_weeks, day)

    def week_dates(self, week: int | None = None) -> list[date]:
        """某一周的 7 个日期，周一在前。"""
        return week_engine.week_dates(self.start_date, self.current_week if week is None else week)

    def week_range_text(self, week: int | None = None) -> str:
        """形如 "9月15日 - 9月21日"。"""
        monday, sunday = week_engine.week_date_range(
            self.start_date, self.settings.total_weeks, self.current_week if week is None else week
        )
        if monday.year == sunday.year:
            return f"{monday.month}月{monday.day}日 - {sunday.month}月{sunday.day}日"
        return f"{monday.year}年{monday.month}月{monday.day}日 - {sunday.year}年{sunday.month}月{sunday.day}日"

    def blocks_for(self, day: date) -> list[dict]:
        """某一天的课程块（含车道布局）。周视图与单日视图共用这一个入口。"""
        return week_engine.blocks_for_date(self.courses, self.settings, day)

    def blocks_of_week(self, week: int | None = None) -> dict[int, list[dict]]:
        """整周的课程块，键为 1..7，供周视图渲染 7 列。"""
        return week_engine.blocks_of_week(
            self.courses, self.settings, self.current_week if week is None else week
        )

    # ------------------------------------------------------------------ #
    # 导航
    # ------------------------------------------------------------------ #

    def clamp_selected(self) -> date:
        """把选中日期夹进学期范围。今天不在学期内时落到最近的学期边界。"""
        return week_engine.clamp_to_semester(
            self.start_date, self.settings.total_weeks, self.selected_date
        )

    def select_date(self, day: date) -> None:
        self.selected_date = week_engine.clamp_to_semester(
            self.start_date, self.settings.total_weeks, day
        )

    def go_today(self) -> None:
        """回到今天；今天不在学期内时落在最近的学期边界周。"""
        self.select_date(date.today())

    def shift_days(self, days: int) -> None:
        """按天移动（单日视图的前一天 / 后一天）。"""
        self.select_date(self.selected_date + timedelta(days=days))

    def shift_weeks(self, weeks: int) -> None:
        """按周移动（周视图的上一周 / 下一周）。

        刻意走"日期 ±7 天"这条路而不是直接改周次，
        这样同一天在星期几上的位置保持不变，视觉上更符合直觉。
        """
        self.shift_days(weeks * 7)

    def can_shift_week(self, delta: int) -> bool:
        """翻到目标周之后是否仍在学期内（用于按钮禁用态）。"""
        target = self.current_week + delta
        return 1 <= target <= self.settings.total_weeks

    def can_shift_day(self, delta: int) -> bool:
        """按天翻到目标日期后是否仍在学期内（用于按钮禁用态）。"""
        target = self.selected_date + timedelta(days=delta)
        return self.is_in_semester(target)

    # ------------------------------------------------------------------ #
    # 课程增删改
    # ------------------------------------------------------------------ #

    def add_course(self, course: Course) -> Course:
        added = self.data.add_course(course)
        self.persist()
        return added

    def update_course(self, course: Course) -> bool:
        changed = self.data.update_course(course)
        if changed:
            self.persist()
        return changed

    def delete_course(self, course_id: str) -> bool:
        removed = self.data.remove_course(course_id)
        if removed:
            self.persist()
        return removed

    def next_course_color(self) -> str:
        return self.data.next_color()

    # ------------------------------------------------------------------ #
    # 学期设置
    # ------------------------------------------------------------------ #

    def update_settings(self, settings: SemesterSettings) -> None:
        """替换学期设置；总周数或开学日期变化后选中日期会被重新夹紧。"""
        self.data.settings = settings
        # 课程里的节次上下界依赖 slots_per_day，设置变化后需要重新规范
        self.data.normalize()
        self.persist()
