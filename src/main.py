"""应用入口。

职责很窄：确定数据目录 → 装载数据 → 搭起外壳 → 订阅状态广播。
所有界面逻辑都在 ui/ 下，所有数据逻辑都在 core/ 下。
"""

from __future__ import annotations

import flet as ft

from core import config, storage
from state import AppState
from ui.app_shell import AppShell


async def main(page: ft.Page) -> None:
    page.title = config.APP_TITLE
    # 本应用的配色是硬编码的浅色方案（白底、浅蓝表头、浅色分隔线），
    # 而 Page.theme_mode 默认是 SYSTEM：一旦系统偏好深色，默认文字色会变成近白色，
    # 落在白底上等于看不见（实测标题、节次序号都会消失）。因此必须锁定浅色模式。
    page.theme_mode = ft.ThemeMode.LIGHT
    # 页面自身不留边距，改由外壳统一控制，这样列宽换算只有一处依据
    page.padding = 0
    page.spacing = 0
    page.bgcolor = "#FFFFFF"

    # 数据目录完全交给 storage 决定：它优先使用 Flet 注入的 FLET_APP_STORAGE_DATA
    # （打包运行时指向应用私有目录），取不到时才回退。
    #
    # 刻意不调用 StoragePaths：它是异步的，而且在 Web 模式下不可用；
    # 实测开发态 Flet 同样会注入 FLET_APP_STORAGE_DATA，
    # 走环境变量这一条路已经覆盖了打包与开发两种情形。
    storage.set_data_dir(None)

    state = AppState()
    state.load()

    shell = AppShell(page, state)
    page.add(ft.SafeArea(content=shell.build(), expand=True))
    # 挂载完成后才允许 update()，这一步同时完成首帧渲染
    shell.on_mounted()

    # 异常兜底：手机上用户看不到任何日志，若异常只打到控制台，
    # 表现就是"点了没反应"，既无法自救也无法反馈。这里把它变成界面上看得见的一行字。
    #
    # 次数上限是必须的：报错处理本身若也抛异常，会经 on_error 再次进来，
    # 变成停不下来的递归。给个预算，花完就彻底安静。
    error_budget = [3]

    def handle_error(event: ft.ControlEvent) -> None:
        if error_budget[0] <= 0:
            return
        error_budget[0] -= 1
        detail = str(getattr(event, "data", "") or "").replace("\n", " ").strip()
        shell.state.set_flash(f"出现错误：{detail[:120]}" if detail else "出现未知错误")

    page.on_error = handle_error

    state.subscribe(shell.refresh)
    page.on_resize = shell.on_resize
    page.update()


ft.run(main)
