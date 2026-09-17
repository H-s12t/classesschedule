"""数据模型：纯数据结构 + 序列化。

刻意不放任何业务计算（周次解析、按周过滤等一律在 week_engine 里），
这样模型层可以被序列化脚本与测试直接使用。

所有带默认值的字段都必须兼容"字段缺失"的旧数据，因此 from_dict 一律用 get + 兜底值。
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from core import config

# 颜色只接受十六进制写法。界面上选色只能从 config.COLOR_PALETTE 里选，
# 所以这里挡的是"被手改过或外部工具写过的数据文件" ——
# 非法颜色会让 Flutter 渲染报错或整个课块变透明，属于看不见但很难排查的故障。
_HEX_COLOR = re.compile(r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$")


def _as_int(value: object, default: int) -> int:
    """尽力把任意值转成 int，失败则返回默认值。

    除了 TypeError / ValueError，还必须接 OverflowError：
    JSON 规范不允许 Infinity / NaN，但 **Python 的 json 默认能解析它们**，
    而 int(float("inf")) 抛的正是 OverflowError。
    """
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        return default


def _as_str(value: object, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _as_list(value: object) -> list:
    """只接受 list / tuple，其余归为空列表。

    **不能写成 `list(value or [])`**：数字或字符串也是"可迭代"或"]非空真值"，
    例如 {"courses": 123} 会在 list() 或 for 上抛 TypeError，
    直接导致应用每次启动都崩在读取阶段。
    """
    return list(value) if isinstance(value, (list, tuple)) else []


def _as_dict(value: object) -> dict:
    """只接受 dict，其余归为空字典（参见 _as_list 的注释）。"""
    return value if isinstance(value, dict) else {}


def _parse_iso_date(value: object) -> date | None:
    """解析 YYYY-MM-DD。刻意不使用 fromisoformat 的宽松分支，避免静默接受怪格式。"""
    text = _as_str(value).strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def session_note_key(day: date | str, course_id: str) -> str:
    """单节课备注的字典键："YYYY-MM-DD|course_id"。

    一门课只属于一个 weekday，所以"某天 + 某课"必定唯一确定一节课，
    不需要再拼节次 —— 否则用户改了课节时间，旧备注就成了找不到主人的孤儿。
    """
    text = day.isoformat() if isinstance(day, date) else _as_str(day)
    return f"{text}|{course_id}"


@dataclass
class SemesterSettings:
    """学期设置：总周数、开学日期、每天节数与各节起止时间。"""

    total_weeks: int = config.DEFAULT_TOTAL_WEEKS
    # ISO 格式 YYYY-MM-DD；留空表示尚未设置，加载时会兜底为"今天所在周的周一"
    start_date: str = ""
    slots_per_day: int = config.DEFAULT_SLOTS_PER_DAY
    # 形如 [["08:00", "08:45"], ...]，长度始终等于 slots_per_day
    slot_times: list[list[str]] = field(
        default_factory=lambda: [list(t) for t in config.DEFAULT_SLOT_TIMES]
    )

    # ---- 派生 ----

    def start_date_obj(self) -> date:
        """返回开学日期；数据残缺时兜底为"今天所在周的周一"，保证上层永远拿到合法日期。"""
        parsed = _parse_iso_date(self.start_date)
        if parsed is not None:
            return parsed
        today = date.today()
        return today - timedelta(days=today.isoweekday() - 1)

    def slot_time(self, slot: int) -> tuple[str, str]:
        """返回第 slot 节（1 起）的起止时间，越界时返回空串而不是抛异常。"""
        index = slot - 1
        if 0 <= index < len(self.slot_times):
            pair = self.slot_times[index]
            if isinstance(pair, (list, tuple)) and len(pair) >= 2:
                return _as_str(pair[0]), _as_str(pair[1])
        return "", ""

    def slot_time_text(self, slot: int) -> str:
        """形如 "08:00\n08:45" 的紧凑两行文案，供窄列显示。"""
        start, end = self.slot_time(slot)
        if not start and not end:
            return ""
        return f"{start}\n{end}"

    # ---- 规范化 / 序列化 ----

    def normalize(self) -> None:
        """把字段夹到合法区间，并把 slot_times 补齐到 slots_per_day 长度。"""
        self.total_weeks = min(
            max(_as_int(self.total_weeks, config.DEFAULT_TOTAL_WEEKS), config.MIN_TOTAL_WEEKS),
            config.MAX_TOTAL_WEEKS,
        )
        self.slots_per_day = min(
            max(_as_int(self.slots_per_day, config.DEFAULT_SLOTS_PER_DAY), config.MIN_SLOTS_PER_DAY),
            config.MAX_SLOTS_PER_DAY,
        )

        # 统一成 [str, str] 结构，长度对齐 slots_per_day
        cleaned: list[list[str]] = []
        for index in range(self.slots_per_day):
            if index < len(self.slot_times):
                pair = self.slot_times[index]
            else:
                pair = None
            if isinstance(pair, (list, tuple)) and len(pair) >= 2:
                cleaned.append([_as_str(pair[0]), _as_str(pair[1])])
            else:
                fallback = (
                    config.DEFAULT_SLOT_TIMES[index]
                    if index < len(config.DEFAULT_SLOT_TIMES)
                    else ("", "")
                )
                cleaned.append([fallback[0], fallback[1]])
        self.slot_times = cleaned

        # 开学日期若填了但格式不对，清空以触发兜底逻辑
        if self.start_date and _parse_iso_date(self.start_date) is None:
            self.start_date = ""

    def to_dict(self) -> dict:
        return {
            "total_weeks": self.total_weeks,
            "start_date": self.start_date,
            "slots_per_day": self.slots_per_day,
            "slot_times": [list(pair) for pair in self.slot_times],
        }

    @classmethod
    def from_dict(cls, raw: object) -> "SemesterSettings":
        data = raw if isinstance(raw, dict) else {}
        settings = cls(
            total_weeks=_as_int(data.get("total_weeks"), config.DEFAULT_TOTAL_WEEKS),
            start_date=_as_str(data.get("start_date")),
            slots_per_day=_as_int(data.get("slots_per_day"), config.DEFAULT_SLOTS_PER_DAY),
            slot_times=_as_list(data.get("slot_times")),
        )
        settings.normalize()
        return settings


@dataclass
class Course:
    """一门课。周次用 int 列表存储，空表示"从不出现"。"""

    name: str = ""
    weekday: int = 1          # 1=周一 … 7=周日
    start_slot: int = 1       # 1 起
    end_slot: int = 1         # 含端点，end >= start
    weeks: list[int] = field(default_factory=list)
    location: str = ""
    teacher: str = ""
    # 课程级备注：默认作用于这门课的所有上课时间（与单节课备注并存显示）
    note: str = ""
    color: str = config.DEFAULT_COURSE_COLOR
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    # ---- 派生 ----

    @property
    def span(self) -> int:
        """占用的课节数，至少为 1。"""
        return max(1, self.end_slot - self.start_slot + 1)

    def is_active(self, week: int) -> bool:
        return week in self.weeks

    def summary(self) -> str:
        """单日视图用的副标题：地点 · 教师，缺项时自动省略。"""
        parts = [p for p in (self.location.strip(), self.teacher.strip()) if p]
        return " · ".join(parts)

    # ---- 规范化 / 序列化 ----

    def normalize(self, slots_per_day: int) -> None:
        self.name = self.name.strip() or "未命名课程"
        self.location = self.location.strip()
        self.teacher = self.teacher.strip()
        self.note = self.note.strip()[: config.MAX_NOTE_LENGTH]

        self.weekday = min(max(_as_int(self.weekday, 1), 1), 7)
        self.start_slot = min(max(_as_int(self.start_slot, 1), 1), slots_per_day)
        self.end_slot = min(max(_as_int(self.end_slot, self.start_slot), self.start_slot), slots_per_day)

        # 周次去重排序，并剔除非正数
        weeks: set[int] = set()
        for value in self.weeks or []:
            number = _as_int(value, 0)
            if number >= 1:
                weeks.add(number)
        self.weeks = sorted(weeks)

        self.color = self.color.strip()
        if not _HEX_COLOR.match(self.color):
            self.color = config.DEFAULT_COURSE_COLOR
        if not self.id:
            self.id = uuid.uuid4().hex[:12]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "weekday": self.weekday,
            "start_slot": self.start_slot,
            "end_slot": self.end_slot,
            "weeks": list(self.weeks),
            "location": self.location,
            "teacher": self.teacher,
            "note": self.note,
            "color": self.color,
        }

    @classmethod
    def from_dict(cls, raw: object) -> "Course":
        data = raw if isinstance(raw, dict) else {}
        course = cls(
            name=_as_str(data.get("name")),
            weekday=_as_int(data.get("weekday"), 1),
            start_slot=_as_int(data.get("start_slot"), 1),
            end_slot=_as_int(data.get("end_slot"), 1),
            weeks=_as_list(data.get("weeks")),
            location=_as_str(data.get("location")),
            teacher=_as_str(data.get("teacher")),
            note=_as_str(data.get("note")),
            color=_as_str(data.get("color")) or config.DEFAULT_COURSE_COLOR,
            id=_as_str(data.get("id")) or uuid.uuid4().hex[:12],
        )
        return course


@dataclass
class ScheduleData:
    """整个学期数据的根对象：设置 + 课程列表 + 单节课备注。"""

    settings: SemesterSettings = field(default_factory=SemesterSettings)
    courses: list[Course] = field(default_factory=list)
    # 单节课备注：键为 "YYYY-MM-DD|course_id"（见 session_note_key）。
    # 与 Course.note（课程级）**并存**，界面上两条都显示。
    # 用稀疏字典而不是给每个日期开字段：一学期只有少数几节课需要额外备注。
    notes: dict[str, str] = field(default_factory=dict)
    version: int = 1

    # ---- 课程增删改 ----

    def get_course(self, course_id: str) -> Course | None:
        for course in self.courses:
            if course.id == course_id:
                return course
        return None

    def add_course(self, course: Course) -> Course:
        course.normalize(self.settings.slots_per_day)
        self.courses.append(course)
        return course

    def update_course(self, course: Course) -> bool:
        existing = self.get_course(course.id)
        if existing is None:
            return False
        course.normalize(self.settings.slots_per_day)
        index = self.courses.index(existing)
        self.courses[index] = course
        return True

    def remove_course(self, course_id: str) -> bool:
        course = self.get_course(course_id)
        if course is None:
            return False
        self.courses.remove(course)
        # 课程没了，它名下的单节课备注也就没有意义了
        self.notes = {
            key: value for key, value in self.notes.items() if not key.endswith(f"|{course_id}")
        }
        return True

    # ---- 单节课备注 ----

    def get_session_note(self, day: date, course_id: str) -> str:
        """某天某节课的备注（没有则返回空串）。"""
        return self.notes.get(session_note_key(day, course_id), "")

    def set_session_note(self, day: date, course_id: str, text: str) -> None:
        """设置某天某节课的备注；传空即删除该键，避免文件里积一堆空串。"""
        key = session_note_key(day, course_id)
        cleaned = text.strip()[: config.MAX_NOTE_LENGTH]
        if cleaned:
            self.notes[key] = cleaned
        else:
            self.notes.pop(key, None)

    def next_color(self) -> str:
        """按已有课程数轮转取色，让相邻新增的课颜色尽量不同。"""
        return config.COLOR_PALETTE[len(self.courses) % len(config.COLOR_PALETTE)]

    # ---- 规范化 / 序列化 ----

    def normalize(self) -> None:
        self.settings.normalize()
        slots = self.settings.slots_per_day
        for course in self.courses:
            course.normalize(slots)

        # 备注重整：丢掉空值，以及课程已不存在的孤儿键
        known_ids = {course.id for course in self.courses}
        cleaned_notes: dict[str, str] = {}
        for key, value in (self.notes or {}).items():
            text = _as_str(value).strip()
            if not text:
                continue
            if key.rsplit("|", 1)[-1] not in known_ids:
                continue
            cleaned_notes[str(key)] = text[: config.MAX_NOTE_LENGTH]
        self.notes = cleaned_notes

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "settings": self.settings.to_dict(),
            "courses": [course.to_dict() for course in self.courses],
            "notes": dict(self.notes),
        }

    @classmethod
    def from_dict(cls, raw: object) -> "ScheduleData":
        data = raw if isinstance(raw, dict) else {}
        schedule = cls(
            settings=SemesterSettings.from_dict(data.get("settings")),
            courses=[Course.from_dict(item) for item in _as_list(data.get("courses"))],
            # 备注值统一转成字符串，键也转成 str：
            # 否则 normalize() 里的 key.rsplit() 会拿到非 str 而报错
            notes={str(key): _as_str(value) for key, value in _as_dict(data.get("notes")).items()},
            version=_as_int(data.get("version"), 1),
        )
        schedule.normalize()
        return schedule
