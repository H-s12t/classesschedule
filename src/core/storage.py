"""JSON 持久化。

关于保存时机：Flet 打包后的应用退出时进程会立即终止，atexit / __del__ /
未 flush 的写入都不保证执行，所以这里**没有**"退出时保存"的设计，
而是提供 save() 供调用方在每次变更后立刻落盘。

写入采用"临时文件 + os.replace"的原子替换，避免写到一半被杀导致 JSON 损坏。
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from core import config
from core.models import ScheduleData

# 由 main.py 在拿到系统应用目录后注入；为空时走回退逻辑
_data_dir: Path | None = None

# 上一次 load() 的重置原因。为空表示读取正常。
# 为什么要有这个：损坏时 storage 只能自己重置数据（不能崩），
# 但"课表被静默清空"是这类工具最糟的失败方式，所以必须让界面能把它报出来。
last_load_warning: str | None = None


def _quarantine(path: Path) -> Path | None:
    """把读不懂的文件改名留档，绝不让"读取失败"演变成"数据被静默覆盖"。

    只保留一份备份就够：重置后写出的文件一定合法，不会连续发生。
    """
    target = path.with_suffix(path.suffix + config.CORRUPT_SUFFIX)
    try:
        path.replace(target)
        return target
    except OSError:
        return None


def _damage_reason(raw: object) -> str | None:
    """结构层面明显不对劲时返回原因，否则 None。

    为什么不能只看"能不能解析"：合法 JSON 也可能字段类型全错，
    而 from_dict 会"平静地"返回一份空数据 —— 用户看不到任何异常，课表却空了。
    静默清空是这类工具最糟的失败方式，所以这种情形必须和解析失败一样隔离 + 告知。
    本应用自己写出的文件永远满足下面的形状，因此判定不会误伤正常数据。
    """
    if not isinstance(raw, dict):
        return "顶层不是对象"
    if "courses" in raw and not isinstance(raw["courses"], (list, tuple)):
        return "courses 不是列表"
    if "settings" in raw and not isinstance(raw["settings"], dict):
        return "settings 不是对象"
    if "notes" in raw and not isinstance(raw["notes"], dict):
        return "notes 不是对象"
    return None


def set_data_dir(path: str | os.PathLike[str] | None) -> None:
    """显式指定数据目录（打包运行时由 StoragePaths 提供）。"""
    global _data_dir
    _data_dir = Path(path) if path else None


def dev_data_dir() -> Path:
    """开发态下 Flet 提供给应用的私有数据目录。

    Flet 会为应用进程注入 FLET_APP_STORAGE_DATA；开发态它指向
    `<app_path>/.flet/storage/data`（app_path 即 pyproject.toml 里的 [tool.flet.app].path）。

    但在 shell 里直接运行工具脚本时并没有这个环境变量，
    如果任由 get_data_dir() 回退到 .devdata，就会出现
    "脚本写了一份数据、应用读的是另一份"的错位。
    因此工具脚本应当显式调用 use_dev_dir() 对齐到同一位置。
    """
    # 本文件位于 <project>/src/core/storage.py，向上两级即 app_path
    app_path = Path(__file__).resolve().parent.parent
    # 这个推导依赖目录层级。若 pyproject.toml 里的 [tool.flet.app].path 被改动，
    # 这里会指向错误位置，而症状是"脚本写的开发数据应用读不到"，极难排查。
    # 因此宁可显式报错，也不要静默写到错的地方。
    if not (app_path / "main.py").is_file():
        raise RuntimeError(
            f"dev_data_dir() 推导出的应用目录不正确：{app_path}（其中没有 main.py）。"
            "若调整过 pyproject.toml 的 [tool.flet.app].path，请同步修改本函数。"
        )
    return app_path / ".flet" / "storage" / "data"


def use_dev_dir() -> Path:
    """把数据目录指向开发态的应用私有目录，供 tools/ 下的脚本使用。"""
    target = dev_data_dir()
    set_data_dir(target)
    return target


def data_dir() -> Path:
    """解析数据目录路径，**不创建它**。

    优先级：显式注入 > FLET_APP_STORAGE_DATA 环境变量 > 工程内开发目录。

    只读场景（例如设置页展示"数据文件在哪里"）必须用这个函数：
    否则光是"看一眼路径"就会在磁盘上留下一个空目录。
    """
    global _data_dir

    if _data_dir is None:
        env_dir = os.getenv("FLET_APP_STORAGE_DATA")
        _data_dir = Path(env_dir) if env_dir else Path.cwd() / config.DEV_DATA_DIR
    return _data_dir


def get_data_dir() -> Path:
    """解析数据目录并确保它存在可写。**仅在读写数据前调用。**

    最后一级兜底到系统临时目录，用于应对两级目录都不可写的极端情况。
    """
    global _data_dir

    target = data_dir()
    try:
        target.mkdir(parents=True, exist_ok=True)
        return target
    except OSError:
        fallback = Path(tempfile.gettempdir()) / "class_schedule"
        fallback.mkdir(parents=True, exist_ok=True)
        _data_dir = fallback
        return fallback


def data_file() -> Path:
    """数据文件路径。同样不创建任何目录。"""
    return data_dir() / config.DATA_FILENAME


def load() -> ScheduleData:
    """读取数据；文件不存在或损坏时返回一份带默认值的新数据。

    两条失败路径都要走这里，而且**一条都不能把异常放出去**：
      1. 文件不是合法 JSON / 不是 UTF-8 → 解析期就抛
      2. 文件是合法 JSON 但**字段类型不对** → from_dict 期才抛
         （例："notes": "abc" 会让 dict() 报 ValueError）

    第 2 条最容易漏：异常发生在解析之后，如果让它冒到 main()，
    应用会**每次启动都崩在同一处**，而用户从界面里无法自救 ——
    只能清空应用数据，等于丢掉整个课表。这是在手机上最不能接受的失败方式，
    所以这里一律兜住，并把原因记到 last_load_warning 供界面展示。
    """
    global last_load_warning
    last_load_warning = None

    path = data_file()
    if not path.exists():
        fresh = ScheduleData()
        fresh.normalize()
        return fresh

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        damage = _damage_reason(raw)
        if damage:
            raise ValueError(f"数据结构异常：{damage}")
        return ScheduleData.from_dict(raw)
    except Exception as exc:  # noqa: BLE001 —— 读取失败绝不能影响启动
        backup = _quarantine(path)
        reason = f"{type(exc).__name__}: {exc}".replace("\n", " ")[:80]
        last_load_warning = f"数据文件无法读取（{reason}），已重置为空课表" + (
            f"，原文件已备份为 {backup.name}" if backup else "，且原文件未能备份"
        )
        fresh = ScheduleData()
        fresh.normalize()
        return fresh


def save(data: ScheduleData) -> None:
    """原子写入。先落临时文件并 flush 到磁盘，再 replace 覆盖正式文件。"""
    data.normalize()
    # 写入前确保目录存在（data_file() 本身不创建目录）
    path = get_data_dir() / config.DATA_FILENAME
    payload = json.dumps(data.to_dict(), ensure_ascii=False, indent=2)

    fd, temp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".schedule-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except BaseException:
        # 任何失败都不能留下垃圾临时文件
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise
