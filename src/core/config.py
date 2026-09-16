"""全局常量：节次时间表、配色、尺寸与路径。

这里的值全部是"出厂默认值"，用户在设置页修改后会把结果写进 schedule.json，
之后以用户数据为准。

本模块不导入任何其它项目模块，也不导入 flet，保证可以被纯逻辑脚本直接使用。
"""

from __future__ import annotations

APP_TITLE = "课程表"

# ---- 持久化 ----
DATA_FILENAME = "schedule.json"
# 读取失败时把坏文件改名保存，方便事后排查
CORRUPT_SUFFIX = ".corrupt"
# 未取到系统应用目录时的回退目录名（用于 PC 开发态）
DEV_DATA_DIR = ".devdata"

# ---- 学期默认值 ----
DEFAULT_TOTAL_WEEKS = 20
MIN_TOTAL_WEEKS = 1
MAX_TOTAL_WEEKS = 30

DEFAULT_SLOTS_PER_DAY = 12
MIN_SLOTS_PER_DAY = 1
MAX_SLOTS_PER_DAY = 16

# ---- 星期 ----
# 内部统一用 isoweekday 语义：1=周一 … 7=周日
WEEKDAY_NAMES = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")
WEEKDAY_SHORT = ("一", "二", "三", "四", "五", "六", "日")

# ---- 12 节默认起止时间 ----
# 上午 4 节、下午 4 节、晚上 4 节，用户可在设置页逐节修改
DEFAULT_SLOT_TIMES: tuple[tuple[str, str], ...] = (
    ("08:00", "08:45"),
    ("08:55", "09:40"),
    ("10:00", "10:45"),
    ("10:55", "11:40"),
    ("14:00", "14:45"),
    ("14:55", "15:40"),
    ("16:00", "16:45"),
    ("16:55", "17:40"),
    ("19:00", "19:45"),
    ("19:55", "20:40"),
    ("20:50", "21:35"),
    ("21:45", "22:30"),
)

# ---- 课程配色 ----
# 新增课程时按已有课程数取模分配，用户可在表单里改
COLOR_PALETTE: tuple[str, ...] = (
    "#4C8DFF",  # 蓝
    "#FF7A59",  # 橙
    "#2EC4B6",  # 青
    "#F5A623",  # 金
    "#8E7CFF",  # 紫
    "#E85D9A",  # 粉
    "#5AC8FA",  # 天蓝
    "#7ED321",  # 绿
    "#D64545",  # 红
    "#00A3A3",  # 墨绿
    "#B07219",  # 棕
    "#6C7A89",  # 灰
)

DEFAULT_COURSE_COLOR = COLOR_PALETTE[0]

# ---- 布局常量（逻辑像素）----
CONTENT_PADDING = 10        # 各页面内容区四周留白，宽度计算必须扣掉它
TIME_COL_WIDTH = 46         # 周视图左侧时间列宽度
WEEK_HEADER_HEIGHT = 36     # 周视图表头高度
WEEK_ROW_HEIGHT = 52        # 周视图每个课节的行高
DAY_TIME_COL_WIDTH = 60     # 单日视图左侧"节次 + 时间"列宽度
DAY_ROW_HEIGHT = 62         # 单日视图每行高度
BLOCK_GAP = 2               # 课程块之间留的缝隙，避免贴死

# 手势判定：横向位移超过该值才算翻页，避免和纵向滚动打架
SWIPE_THRESHOLD = 60.0

# Flet 尚未完成首帧布局时 page.width 可能为 0，用这个值兜底
FALLBACK_PAGE_WIDTH = 390.0
