# 课程表工具 — 计划与进度

> 目标平台：HarmonyOS 4.3.0（可安装 APK）
> 技术路线：Python + Flet
> 最后更新：2026-09-16

---

## 0. 协作约定（重要，优先于其他内容）

### 0.1 文件改动范围限制

- **只允许在 `/mnt/d/class_schedule` 目录内新增、修改、删除文件。**
- **不得改动该目录之外的任何文件**，包括但不限于：`/home/h/...`、`/tmp/...`、
  系统配置、其他工程目录、用户主目录下的其他内容。
- **唯一例外：安装必要的依赖库。** 需要安装 Python 包、系统软件包或其他依赖时，
  **必须先向用户询问并取得同意**，不得自行安装。
  此例外同样适用于为了满足依赖而不得不落在项目目录之外的运行环境（见 0.2）。

### 0.2 历史越界记录（已全部关闭）

搭建开发环境阶段曾有内容落在 `/mnt/d/class_schedule` 之外，现已清理完毕：

| 位置 | 内容 | 处置 |
|---|---|---|
| `/home/h/.venvs/class_schedule` | Python 虚拟环境（187 MB，flet 1.0.0） | **已删除**（经用户确认）。开发环境已迁入工程内 `./.venv`，见 4.6 |
| `/tmp/cs-startup.log` | 一次性启动诊断输出 | **确认从未生成**（当时热重载未生效，那段代码从未执行），写入代码亦已删除 |

顺带删除了因变空的 `~/.venvs` 父目录（也是当初为放 venv 而创建的）。

**当前状态：目录外已无任何项目相关内容，0.1 节的约束不存在实际例外。**
以下内容保留为历史记录，方便日后追溯。

### 0.3 其他约定

- 引入新的第三方依赖前需要先询问；当前刻意只依赖 `flet` 与标准库。
- 构建产物、演示数据等生成物一律落在工程目录内。

---

## 1. 项目概况

### 1.1 需求

1. 能在 HarmonyOS 4.3.0 上运行的课程表工具
2. 使用 Python，多文件结构
3. 每学期周数可设置
4. 手动添加课程：课程名、上课周次、上课地点（图形界面）
5. 以周为单位展示，可翻页
6. 非本周的课程不显示

### 1.2 已确认的关键决策

| 项 | 决定 |
|---|---|
| 技术路线 | Flet（Python + Flutter 渲染），打包为 APK |
| 节次结构 | 每天固定 12 节；一门课可跨多个连续节次（起止节次） |
| 当前周来源 | 按开学日期自动推算 |
| 视图 | 周视图 + 单日视图，底部导航栏切换，两者双向联动 |
| 翻页交互 | 周视图：滑动 + 按钮；**单日视图：只保留按钮**（滑动专属周视图） |
| 单日视图时间 | 显示每节起止时间（取学期设置里的时间表） |
| 空白节次新增 | 单日视图点空白节次 → 表单预填该星期与该节次 |
| 回到今天 | 两视图共用入口；今天不在学期内时落在最近的学期边界周 |
| 依赖 | 只保留 `flet` + 标准库，不引入需要 Android 轮子的第三方库 |

### 1.3 为什么选 Flet（调研结论）

- 构建宿主支持 macOS / Linux / Windows；缺失的 Flutter SDK、JDK 17、Android SDK 会**自动安装**
- 使用官方预编译的 CPython，**不需要自己编译 CPython 与 recipes**
  （这是 Kivy/Buildozer 路线和 Qt 路线的主要风险来源，而 Qt 的 `pyside6-android-deploy`
  内部反而就是调用 buildozer）
- 中文走系统字体链路，**零配置**；Kivy 不内置中文字体，必须自带并注册
- 真机日志可读：stdout/stderr 输出到 logcat 的 `flet.python` tag
- 支持 `flet run --web`，可在无显示器的环境下验证界面

---

## 2. 完整计划

### Phase 1 — 数据层、周次引擎与共享状态（不依赖 Flet，可独立验证）

1. 按 Flet 工程规范建骨架：`pyproject.toml`、`README.md`、`src/main.py`、`src/core/`、`src/ui/`
2. `core/models.py`：`Course`（课名、星期 1-7、起始节次、结束节次、上课周次集合、地点、教师、颜色）、
   `SemesterSettings`（总周数、开学日期、每天节数、各节起止时间）、`ScheduleData`，均带序列化方法
3. `core/week_engine.py`：当前周推算、周次表达式解析、`is_active()`、`courses_of_week()`、
   `courses_of_day()`、翻页夹紧，以及日期与周次互推的 `week_of_date()`、`date_of_week_day()`、
   `week_date_range()`、`clamp_to_semester()`
4. `core/storage.py` + `core/config.py`：JSON 持久化（原子写入），根目录走应用私有目录；
   `config.py` 放 12 节默认时间表与预设色板
5. `src/state.py`：`AppState` 持有数据、`selected_date`（唯一真相源）与刷新订阅；
   数据变更先落盘再广播

### Phase 2 — 周视图

6. `ui/schedule_view.py`：表头与主体都是"固定宽时间列 + 7 个等分星期列"；
   每个日列内部是高度为 `12 × 行高` 的 `Stack`，课程块用
   `top = (起始节次-1) × 行高`、`height = 节数 × 行高` 定位
7. `ui/week_nav.py` 的能力并入 `schedule_view.py`：周次导航、上一周/下一周（到边界禁用）、
   回到今天、横向滑动翻页、点某天列切到单日视图

### Phase 3 — 单日视图与导航

8. `ui/day_view.py`：日期导航（**仅按钮**）、12 行纵向列表、左侧"节次 + 起止时间"列、
   跨节次课程合并为整块、空白节次可点击新增
9. `ui/app_shell.py`：底部 `NavigationBar` 三项（课表 / 单日 / 设置）、视图调度、刷新分发

### Phase 4 — 录入表单与学期设置

10. `ui/week_picker.py`：1..总周数 的复选网格 + 全选 / 单周 / 双周 / 清空
11. `ui/course_form.py`：新增与编辑共用，支持外部预填（星期、起止节次）；校验并落盘
12. `ui/settings_view.py`：总周数、开学日期、每天节数、每节起止时间

### Phase 5 — PC 联调

13. 用热重载跑通：录入 → 两视图切换 → 翻页 → 强杀重启，覆盖边界场景

### Phase 6 — 打包上手机

14. 真机预检：`adb shell getprop ro.build.version.sdk` 确认 API level 后定 minSdk/targetSdk
15. 配置 `pyproject.toml` 的 `[tool.flet]`（产品名、org、版本、`target_arch=["arm64-v8a"]`、
    Android min/max SDK、boot screen）
16. 打包：**推荐在 Windows 侧**执行（工作区在 D 盘，可绕开 WSL 挂载盘的权限问题）；
    在 WSL 内则先同步到 `~/` 原生目录（已写成 `tools/package_android.sh`）
17. 装机验证：Windows 侧 adb 安装 + `adb logcat -s flet.python` 读日志

---

## 3. 当前进度

### 3.1 已完成并通过验证

| 阶段 | 状态 | 证据 |
|---|---|---|
| Phase 1 数据层与周次引擎 | ✅ 完成 | `tools/selfcheck.py` **66 项断言全部通过** |
| Phase 2 周视图 | ✅ 完成 | 界面已实际渲染并截图确认 |
| Phase 3 单日视图与导航 | 🟡 代码完成 | `tools/check_views.py` 控件树校验通过；界面渲染待验证 |
| Phase 4 表单与设置 | 🟡 代码完成 | 设置页已确认渲染；表单弹层交互待验证 |
| Phase 5 PC 联调 | 🔴 进行中 | 见第 4 节 |
| Phase 6 打包 | ⬜ 未开始 | — |

### 3.2 `selfcheck.py` 覆盖的验证项（全部通过）

1. 周次表达式解析：`1-16`、`1,3,5`、`1-16单`、`5双`、`全`、倒序区间、去重、
   超范围剔除、乱输容错、全角连接符
2. 日期与周次互推、学期边界夹紧（开学前 / 超期末 / 整周日期不塌缩）
3. **两视图一致性交叉校验**：遍历学期内 **140 天**，断言"按周分组"与"按日过滤"
   对同一天给出完全相同的课程集合 —— 防止两条渲染路径逻辑分叉
4. "非本周不显示"：`数据结构` 仅第 5-8 周出现，第 3/9 周不出现
5. 车道分配：同一时段两门完全重叠 + 一门部分重叠 → 3 条车道；不重叠时 lane_count = 1
6. 序列化往返幂等 + 脏数据容错
7. 持久化原子写入、损坏文件留档并回退默认数据

### 3.3 已确认的渲染效果

**已实测（截图确认）**

- 周视图：周次导航（"第 1 周（共 20 周）"）、日期范围、"本周/未到"提示、
  **今天所在列高亮**（不在该周时正确消失）、左侧节次时间列、12 行网格与分隔线、
  周末列底色区分、底部导航栏
- **课程块正常渲染**：课名与地点显示在块内，跨节次课程正确占满整段
  （高等数学 周一 1-2 节、大学英语 周三 3-4 节、线性代数 周四 5-6 节）
- **"非本周不显示"已视觉验证**：数据结构（第 5-8 周）、概率论（第 3-6 周）、
  物理实验（双周）在第 1 周均不出现
- 单日视图：日期文案与周次、节次时间列、课程块详情（课名 + 地点·教师 + 节次范围）、
  空状态"这一天没有课"、空白节次可点击
- **两视图联动双向均验证通过**：周视图点某天列 → 单日视图定位该日；
  单日视图连点"后一天"7 次跨入第 2 周 → 切回周视图正确显示"第 2 周"与对应日期范围
- **表单预填与落盘验证通过**：点空白节次弹出表单，星期与起止节次已按点击位置预填；
  填写课名保存后，课程同时出现在两个视图中，且已真实写入磁盘 JSON 文件
- **编辑课程验证通过**：点课程块 → 表单带出全部原有数据（课名、星期、起止节次、
  地点、教师、周次勾选）；改名保存后，两视图与磁盘文件同步更新
- **删除课程验证通过**：编辑表单的"删除"→ 二次确认弹层（正确插入课程名）→ 确认后
  课程消失、周视图对应列变空、磁盘文件课程数 8→7，两个弹层均正常关闭
- **周次多选的数据绑定经无障碍树确认**：高等数学 1-18 周 → 复选 1-18 勾选、19-20 未勾选，
  摘要显示"已选 18 周：1-18"（区间压缩正确）
- 设置页：全部字段与按钮渲染正常

**尚未实测**

- 保存失败提示路径（R2 的修复效果需要构造磁盘异常才能验证）
- 真机（Android / HarmonyOS）上的全部表现

### 3.4 已建立的开发辅助工具

| 文件 | 用途 |
|---|---|
| `tools/selfcheck.py` | 核心层自测（66 项断言），不依赖 flet |
| `tools/check_views.py` | 控件树校验，不需要浏览器即可断言课程块数量与几何 |
| `tools/seed_demo.py` | 生成演示数据（覆盖跨节次、重叠车道、单双周等场景） |
| `tools/probe_flet_api.py` | 探测当前 Flet 版本可用的控件与枚举 |
| `tools/probe_flet_signatures.py` | 探测控件构造签名 |
| `tools/package_android.sh` | 同步到 WSL 原生目录并构建 APK |

---

## 4. 已知问题与待办

### 4.1 课程块未渲染 —— 已定位并修复（根因与最初判断不同）

**结论：应用本身的存储逻辑是正确的，问题出在"开发脚本写入的位置"与"应用读取的位置"错位。**

#### 实测证据（启动诊断输出）

```
FLET_APP_STORAGE_DATA='/mnt/d/class_schedule/src/.flet/storage/data'
FLET_APP_STORAGE_TEMP='/mnt/d/class_schedule/src/.flet/storage/temp'
cwd=/mnt/d/class_schedule/src/.flet/storage/data
StoragePaths 不可用
最终 data_file=/mnt/d/class_schedule/src/.flet/storage/data/schedule.json
课程数=0
```

#### 真实根因

1. **Flet 即使在开发态也会注入 `FLET_APP_STORAGE_DATA`**，开发态指向 `<app_path>/.flet/storage/data`
2. `core/storage.get_data_dir()` 优先使用该环境变量（这是正确行为，Android 上就靠它拿到应用私有目录）
3. 但我写的 `tools/seed_demo.py` 默认把演示数据写到了工程内的 `.devdata/schedule.json`
4. 于是**应用读 A 文件、脚本写 B 文件**，课程数恒为 0——不是渲染失败，是数据真的为空

#### 最初判断错在哪里

曾怀疑"`StoragePaths` 在 Web 模式下返回了异常目录并覆盖了本地目录"。
实测表明 `StoragePaths` 在 Web 模式下**确实按文档所述不可用**（抛出异常，被正常捕获），
并没有返回异常目录。真正的问题与它无关。

诊断之所以一度难以推进，是因为设置页显示的"20 周 / 12 节 / 2026-09-14"
与默认兜底值完全相同，无法据此判断数据是否被读取。

#### 已实施的修复（应用逻辑无需改动）

| 文件 | 改动 |
|---|---|
| `src/core/storage.py` | 新增 `dev_data_dir()` 与 `use_dev_dir()`：显式推导出 Flet 开发态使用的应用数据目录，供工具脚本对齐 |
| `tools/seed_demo.py` | 默认写入应用实际读取的目录（不再写 `.devdata`）；新增 `--show` 只打印路径 |
| `tools/check_views.py` | 改用 `storage.use_dev_dir()`，与上面保持一致 |
| `src/main.py` | 删除 `StoragePaths` 调用与全部临时诊断代码；`storage.set_data_dir(None)` 即可，剩余逻辑交给 `get_data_dir()` |
| `pyproject.toml` | 新增 `[tool.flet.app].exclude`，把 `.flet` 等开发期目录排除出打包产物 |

#### 已完成的端到端确认

修复已应用，并**已完成视觉确认**：写入演示数据后重新加载页面，
周视图正确显示 4 个彩色课程块（含跨节次），单日视图与设置页均正常。
详见 3.3。

关键前提：`tools/seed_demo.py` 与应用读的是**同一份**数据文件；
若两边不一致，就会出现"脚本写了数据、界面里没课"的假象（这正是本节的教训）。

### 4.2 待办清单

**已完成**

- ✅ 定位并修复"课程块未渲染"（根因见 4.1，应用逻辑本身无需改动）
- ✅ 删除 `src/main.py` 中的临时诊断代码与多余的 `StoragePaths` 调用
- ✅ 把 `.flet` 等开发期目录排除出打包产物
- ✅ 清理已弃用的 `.devdata/` 目录（含过期演示数据与诊断日志）
- ✅ 确认 `/tmp/cs-startup.log` **从未生成**，目录外遗留项已关闭（见 0.2）
- ✅ 完成一轮风险检查，结论见 4.3

**本轮已实施的具体变更**

| 文件 | 变更 | 对应问题 |
|---|---|---|
| `src/ui/layout.py` | 新增 `is_on_page()`：自行沿 parent 链查找 Page，替代会抛异常的 `.page` 探测 | R1 |
| `src/ui/week_picker.py` | 摘要刷新改用 `layout.is_on_page()` | R1 |
| `src/ui/app_shell.py` | 去掉手写挂载标志，改用 `layout.is_on_page()`，消除"忘记调用即静默失效"的隐患 | R1 |
| `src/state.py` | `persist()` 捕获 `OSError`，经提示条告知"保存失败，改动未写入磁盘"，并返回是否成功 | R2 |
| `pyproject.toml` | 排除项改为逐条列出嵌套 `__pycache__`（精确匹配、不支持通配符） | R3 |
| `tools/package_android.sh` | 同步阶段增加排除 `.flet`、`dist` | R4 |
| `tools/check_views.py` | 改为自带内存样本，不再依赖磁盘数据文件（无数据时不再误报失败） | R7 |
| `src/main.py` | 显式锁定 `ThemeMode.LIGHT` | R14 |
| `src/ui/course_form.py` | 表单尺寸按页面自适应 | R15 |
| `src/core/storage.py` | 拆分 `data_dir()`（不创建）/ `get_data_dir()`（确保存在），只读展示不再产生目录 | R16 |

**待办（按优先级）**

1. ~~修复 4.3 的 R1、R2~~ ✅ 已完成
2. ~~修正 4.3 的 R3、R4~~ ✅ 已完成（并顺带修了 R7、R14、R15、R16）
3. ~~完成课程块的端到端视觉确认~~ ✅ 已完成（见 3.3）
4. ~~处置工程内那个失效的 `.venv/`~~ ✅ 已完成（已装 `flet[cli,web]` 并启用为开发环境，见 4.6）
5. ~~在界面上实测编辑与删除课程~~ ✅ 已完成
6. ~~实测单日视图~~ ✅ 已完成
7. ~~实测两视图联动~~ ✅ 已完成（双向）
8. ~~实测持久化~~ ✅ 已完成（新增课程已真实写入磁盘）
9. **真机验证 `FLET_APP_STORAGE_DATA` 确实被注入**（R6，数据持久化的唯一依据）
10. 真机 API level 预检（`adb shell getprop ro.build.version.sdk`）
11. Phase 6 打包与真机验证
12. ~~处理 4.3 中剩余的 R5、R8~R13~~ ✅ 已处理（R5/R8/R10/R11 修复；R9/R12/R13 已定处置方式，见 4.4）
13. ~~待构建完成后重新构建一次，确保 APK 包含本轮源码改动~~ ✅ 已完成（现有 build 3，见第 17 轮）

**当前未完成（按优先级）**

1. 🔴 **真机安装疑似无效**（见 9.6）：用户多次安装、卸载重装后手机仍跑最初版本。
   已加入"设置页显示版本号"作为可判定锚点，待用户装 build 3 后回报结果。
   若仍不行，排查方向转为传输/安装路径本身（最可疑：同名旧文件未覆盖、
   或从 GitHub Release 下载了旧附件）
2. 🟠 **删除三层嵌套的自身副本**（见 9.7）：`class_schedule/` 向下三层，
   共约 6 个旧文件副本（含 `src/` 与 `pyproject.toml`）。
   原因已定位且已加护栏，但删除属破坏性操作，**先征求用户同意**
3. 🟠 **Release 附件仍是第 10 轮那一版**（见 9.5）：需要把 build 3 的
   `class_schedule.apk` + `.sha1` 重新上传（建议用唯一命名，避免下载端缓存旧文件）
4. 🟡 **安全审计剩余待决策项**（见第 16 轮）：B1 release 用 debug 签名、
   B2 INTERNET/ACCESS_NETWORK_STATE 权限、B3 打包了 16 个无用插件、
   B4 `allowBackup` 默认 true、B6 临时目录静默回退、B7 未 fsync 目录、
   B8/B9 返回手势未处理

### 4.3 风险检查结果（2026-09-16，逐项有代码位置佐证）

**状态速览**：R1–R5、R7、R8、R10–R16 **已修复**；
R17–R20、R22–R27 **已修复/已绕开**（打包链路与环境，见 4.4）；
R21 为 **flet_cli 自身缺陷，已绕开**；
R6 **真机验证通过**（应用可运行、数据落私有目录、强停后持久，见 9.4）；
R9、R12、R13 **已评估并决定处置方式**（见 4.4）。

**全部风险项均已关闭**（R1–R27），无待验证项。

**APK 已成功产出**：`build/apk/class_schedule.apk`（50 MB，552 个条目）——见第 9 节。

#### R1 · 代码缺陷 · `Control.page` 探测写法无效（同已踩过的坑）

- 位置：`src/ui/week_picker.py:60` — `if summary is None or summary.page is None:`
- 问题：Flet 1.0 的 `Control.page` 在未挂载时**抛 `RuntimeError`**，不会返回 `None`。
  这行代码本意是"未挂载就跳过"，实际效果是"未挂载就崩溃"。
- 这正是 4.1 之前让应用首帧直接报错的那个坑，同一个错误写法又出现在了这里。
- 当前状态：**潜伏未触发** —— 已确认 `set_value()` 在现有代码中从未被调用，
  而 `_refresh_summary()` 只在用户交互（必然已挂载）后触发。
- 修法：改用在 `AppShell` 中已验证有效的显式挂载标志，不再用 `.page` 探测。

#### R2 · 代码缺陷 · 落盘失败无任何保护与提示

- 位置：`src/core/storage.py:112` 的 `save()` 在 `except BaseException` 中清理临时文件后**重新抛出**；
  调用链 `state.py:56 persist() → storage.save()` 上游没有任何 `try/except`
- 影响：手机上磁盘满 / 权限异常时，异常会直接抛进 Flet 事件处理器，
  用户只会看到界面无反应或会话中断，**且不知道自己刚保存的课程已经丢了**
- 落盘调用点共 4 处：新增 / 修改 / 删除课程、保存学期设置（`state.py:170/176/182/197`）
- 建议：`persist()` 捕获 `OSError` 并通过已有的 `set_flash()` 机制提示"保存失败"

#### R3 · 打包配置 · `__pycache__` 排除实际未生效

- 位置：`pyproject.toml` — `exclude = [".flet", "devdata", ".devdata", "__pycache__"]`
- 依据：Flet 文档明确"路径按 app path 精确匹配，不支持通配符"。
  因此 `__pycache__` **只能匹配 `src/__pycache__`**，匹配不到嵌套的。
- 实测工程内实际存在三个：`src/__pycache__`（可匹配）、
  **`src/core/__pycache__`、`src/ui/__pycache__`（匹配不到）**
- 影响：开发机 Python 3.12 编译出的 `.pyc` 会被打进 APK，属无用体积，
  并可能与构建期重新编译的字节码混淆
- 另：`devdata` / `.devdata` 位于工程根目录而不在 app path（`src`）下，这两项是无意义的空条目

#### R4 · 打包脚本 · 同步阶段未排除 `.flet`

- 位置：`tools/package_android.sh` 的 rsync/tar 排除列表只含
  `.venv`、`.devdata`、`build`、`__pycache__`
- 影响：`src/.flet/`（Flet 开发态运行时目录，实测 12K，含临时 html/json）会被同步到构建目录。
  最终是否进入 APK 取决于 pyproject 的排除项（当前已排除），但同步阶段就排除更干净

#### R5 · 环境不一致 · 开发与打包用的 Python 小版本不同

- `pyproject.toml` 的 `requires-python = ">=3.12,<3.14"` 会让 Flet 选用 **3.13** 作为内置运行时，
  而本地开发环境是 **3.12.3**
- 当前代码在两者上都兼容（未使用 3.13+ 专有语法），但这是一类容易被忽略的偏差来源
- 建议：明确锁定单一小版本，让开发与设备端一致

#### R6 · 未验证的关键假设 · 打包后 `FLET_APP_STORAGE_DATA` 是否被注入 ✅ 真机验证通过

- 数据持久化完全依赖这一条：`get_data_dir()` 优先读该环境变量；
  取不到时回退 `Path.cwd()/.devdata`（文档称 Android 上 cwd 即应用私有支持目录，
  因此回退理论上仍然安全，但会落到 `.devdata` 子目录）
- 影响：若假设不成立，用户的课程数据会写到一个意料之外的位置
- **实测结果（2026-09-17，真机）**：
  1. APK 安装后 **应用可正常运行** —— 这同时反证了 R27 的修复有效：
     若 `flet` 未打进 `sitepackages.zip`，启动即 `ModuleNotFoundError` 闪退
  2. 设置页显示的数据文件路径为
     `/data/user/0/com.example.class_schedule/files/data/schedule.json`
     → **落在应用私有目录**，环境变量已被注入（**不是** `.devdata` 回退路径）
  3. **强制停止后数据依然在** → 即时保存策略有效
- **附带确认的细节**：`data_dir()` 直接返回 `FLET_APP_STORAGE_DATA` 的值，
  `data_file()` 再拼 `schedule.json`。设备上最终路径多带了一层 `data/`，
  说明 Flet 注入的值本身即 `.../files/data`（而非 `.../files`）
- **结论**：假设成立，`.devdata` 回退分支在生产中不会触发（保留作安全网）

#### R7 · 工具可用性 · `check_views.py` 在无数据时以退出码 1 结束

- 现象：清理掉演示数据后，该脚本输出"没有演示数据，请先运行 tools/seed_demo.py"并返回 1
- 影响：容易被误读成"校验失败"，实际只是前置数据缺失
- 建议：无数据时自行调用 seed 逻辑，或作为"跳过"并返回 0

#### R8 · 可用性 · 12 节 × 7 列在竖屏下每列约 44px ✅ 已处置（接受折行换大字号）

- 课程块内只放得下课名，地点与教师由单日视图承担（已按此设计）
- **空间硬约束**（手机 390px 实测计算）：

  ```
  content_width = 390 - 10*2 - 8 = 362
  column_width  = (362 - 46) / 7 = 45.1px
  文字可用宽     = 45.1 - 8(块内边距) = 37px
  ⇒ 4 个汉字单行显示要求字号 ≤ 37/4 = 9.25px
  ```

- **最终方案**（用户选定）：接受周视图课名折行，换取更大字号（各 +2）。
  现取值：课名 **12 / 11 / 10**（按列宽分档）、单日视图 **14**；
  地点 **10**、单日详情与节次 **12**
- **代价**：手机上 4 字课名不再单行显示。示例数据均为多节连排（1-2 / 3-4 / 5-6 节），
  块高充足，折行后仍完整可读；仅"单节 + 长课名"会显局促
- **已实测验证**（浏览器 390×844）：单日视图层次清晰无截断；周视图折行但不丢字
- 注：只要字号 >9px 就必然折行，**这是每列 45px 的空间决定的，调参无法绕过**

#### R9 · 交互 · 横向滑动翻页与纵向滚动的竞争

- 已设 60px 位移阈值，且按钮翻页始终可用（兜底不会导致功能缺失）
- 真机上需实测手感；若不稳定可只保留按钮

#### R10 · 交互 · 旋转屏幕会重建页面，编辑中的设置输入会丢失

- `app_shell.on_resize()` 在宽度变化时重建当前页
- 已确认**软键盘弹出只改变高度**，而该守卫只比较宽度，因此不会触发重建 —— 这点是安全的
- 残余风险仅限设备旋转（本应用目标是竖屏）

#### R11 · 耦合 · `dev_data_dir()` 依赖目录层级

- `src/core/storage.py` 的 `dev_data_dir()` 通过 `__file__` 向上两级推导 app path
- 若将来调整 `pyproject.toml` 里的 `[tool.flet.app].path`，此处会**静默失效**
- 建议：加一条断言或注释说明该耦合

#### R12 · 布局 · 首帧 `page.width` 为 0

- 列宽由页面宽度换算而来，而首帧布局完成前拿不到真实宽度
- 已用兜底值（390）+ `on_resize` 补一次重绘来覆盖
- 残余影响：首帧可能有一瞬间列宽不正确，随后自动纠正

#### R13 · 交付 · 装机与系统升级

- 侧载安装需关闭"纯净模式"并允许外部来源
- **最大不可控风险**：若该设备日后升级到 HarmonyOS NEXT（5.x），APK 将不再被支持，
  整条技术路线作废，需改为 `.hap` 方案重做界面层（数据层与周次引擎可复用）

#### R14 · 严重显示缺陷 · 主题跟随系统导致文字几乎不可见 ✅ 已修复

- 现象：底部导航栏突然变成深色；"第 1 周（共 20 周）"标题、节次序号、周次提示
  在白色背景上**几乎看不见**（同一份代码先后两次截图，配色完全不同）
- 根因：`Page.theme_mode` 默认为 `ThemeMode.SYSTEM`（已用 `inspect.signature` 确认）。
  系统偏好深色时，未显式指定颜色的文字会取深色主题的"近白色"前景色，
  而本项目的配色是**硬编码浅色方案**（白底、浅蓝表头、浅色分隔线）→ 白字落白底
- 影响面：所有未显式设置 `color` 的文字，包括周次标题、节次序号、
  设置页标题、周次多选项标签
- 修复：`src/main.py` 显式设置 `page.theme_mode = ft.ThemeMode.LIGHT`
- 教训：硬编码配色的界面**必须锁定主题模式**，不能依赖系统偏好

#### R15 · 布局缺陷 · 表单尺寸硬编码，矮视口下内容被裁切 ✅ 已修复

- 位置：`src/ui/course_form.py` 原为 `_FORM_WIDTH = 340` / `_FORM_HEIGHT = 430`
- 现象：在 401px 高的视口里，对话框内容区被压到放不下，
  "上课地点"只露出半截，底部的颜色选择与周次多选够不到
- 影响：手机横屏、小屏机型同样会踩到
- 修复：改为 `_form_size(page)`，按页面尺寸自适应——
  高度取 `页面高度 × 0.70` 并夹在 220~430 之间，宽度取 `页面宽度 - 40` 并夹在 240~340；
  实测 632×401 → 340×281、412×860 → 340×430、915×412 → 340×288、未知尺寸 → 340×430

#### R16 · 设计缺陷 · 只读展示路径会产生目录副作用 ✅ 已修复

- 位置：`src/core/storage.py` 的 `data_file()` 内部调用 `get_data_dir()`，后者会 `mkdir`
- 现象：**光是渲染设置页（展示"数据文件"路径）或运行 `check_views.py`，
  就会在磁盘上创建出 `.devdata/` 目录** —— 清理完又被凭空创建出来
- 修复：拆分为 `data_dir()`（只解析、不创建，供只读展示）与
  `get_data_dir()`（确保存在，仅供读写前调用）；`data_file()` 改用前者
- 验证：删除 `.devdata` 后运行 `check_views.py`（它会展示该路径），确认目录不再出现

### 4.4 本轮变更（R5 / R8 / R10 / R11）与 R9 / R12 / R13 的处置

#### 已修复

| 问题 | 改动 | 验证方式 |
|---|---|---|
| **R5** Python 版本偏差 | `pyproject.toml` 的 `requires-python` 由 `">=3.12,<3.14"` 改为 `">=3.12,<3.13"`，使打包内置运行时（3.12）与开发环境（3.12.3）一致 | 配置层面确认；最终以打包日志中的 Python 版本为准 |
| **R8** 窄列可读性 | `ui/layout.py` 新增 `name_font_size()` 与 `shows_secondary_line()`：按列宽在 8/9/10 三档选字号，列宽 < 42px 时不再显示地点 | 实测各宽度取值：48px → 字号 9 + 显示地点；29px → 字号 8 + 隐藏地点，课名仍可换行阅读 |
| **R10** 旋转丢输入 | `ui/app_shell.py` 的 `on_resize()` 在设置页直接返回：设置页布局不依赖列宽换算，重建只会丢掉编辑中的输入 | **实测通过**：在设置页输入 `18` 后把宽度从 632 改为 900，值仍为 `18` 且输入框保持焦点（说明未重建） |
| **R11** 路径推导静默失效 | `core/storage.py` 的 `dev_data_dir()` 增加守卫：推导出的目录下没有 `main.py` 就直接报错，不再静默写到错位置 | 正常路径返回值正确；报错分支为配置变更时的保护 |

#### 已评估但决定不改代码

- **R9（滑动与滚动竞争）**：当前已用 60px 位移阈值，且按钮翻页始终可用，
  **不会因手势识别失败而丢功能**。手感必须真机才能判断，因此保留现状，
  待真机实测后再决定是否需要同时引入速度判定。
- **R12（首帧宽度为 0）**：属**瞬时显示**问题（首帧用 390 兜底，`on_resize` 立即校正），
  没有不靠猜的替代方案（客户端宽度只有在连接后才拿得到），
  因此作为已知的良性限制保留。若将来需要彻底消除，可改为"宽度未知时用 stretch 定位"。
- **R13（装机与系统升级）**：无法用代码解决，已转为**安装前的检查清单**（见 4.5）。

#### R17 · 打包链路的两项实测发现（新增）

- **从 WSL 调用 Windows 交互式 CLI 时，stdin 吃不到输入**：
  `flet build` 会问 "Flutter SDK 3.44.8 is required... Proceed? [y/n]"，
  用 `send_to_terminal` 发 `y` **无效**，进程会一直挂在那里且不下载任何东西。
  **正确做法：直接用 `--yes` 参数**（"Answer yes to all prompts"）。
- **重定向输出时 `flet build` 的日志会是 0 字节**：Python 输出重定向到文件后是块缓冲，
  攒够才刷盘。因此**判断构建进度必须看文件系统**（`~/flutter/`、`~/java/`、临时目录里的 zip、
  `build/` 目录），不能看日志。
- 另一个曾经误导过我的坑：**看进程内存判断下载是否停滞是无效的**，
  下载型任务的驻留内存基本不变；应当看目标文件的**修改时间**（如果等于当前时刻，就是在实时写入）。

#### R18 · 打包链路 · rich 向 GBK 控制台打印 emoji 导致构建中断 ✅ 已修复

- **现象**：`flet build apk --yes` 退出码 1，无任何 APK 产出，工具链却已装好
- **根因**：**与应用代码无关**。`rich` 判断当前是"传统 Windows 控制台"，
  于是走 `legacy_windows_render` 用 Win32 API 直接写入，编码取**系统代码页**
  （中文 Windows = GBK/cp936）。崩溃点是
  `flet_cli/commands/build_base.py:1943` 打印 `Created app shell ✅`，
  而 ✅（U+2705）不在 GBK 字符集内，于是 `UnicodeEncodeError`
- **误导性**：真实异常发生在 `Live.__exit__` 的收尾流程里，
  第二个 traceback（`rich/live.py` → `_write_buffer`）**覆盖了第一个真实 traceback**，
  只看日志末尾会误判成"rich 的 Live 上下文管理器有问题"
- **修复**：加 `--no-rich-output`。帮助原文即写明适用场景：
  *"Disable rich output and prefer plain text. **Useful on Windows builds**"*，
  等价环境变量 `FLET_CLI_NO_RICH_OUTPUT`。该模式下 ✅ 被替换为纯文本 `OK`，编码冲突消失
- **附带好处**：同时缓解了 R17 的"日志 0 字节"问题——
  关闭 rich 的 `Live` 全屏刷新后，输出变为普通行式打印，重定向到文件也能及时读到进度
- **结论**：**Windows 上构建 Flet 应用应始终带 `--no-rich-output`**，
  这不是可选项而是中文 Windows 环境下的必需项

#### R19 · 环境 · GitHub 被 Steam++ 写成 127.0.0.1，导致运行时下载失败 ✅ 已定位（需用户操作恢复）

**现象**：`flet build apk` 在 `Packaging Python app...` 阶段失败，
报 `Flet app package was not staged to build\python-app.`，且该目录未生成。
这个报错本身没有任何信息量，下面两层原因都是挖出来的。

**第一层：缓存目录中毒**（`serious_python/bin/package_command.dart:756`）

```dart
if (!await _pythonDir!.exists()) {   // ← 目录存在就整体跳过下载+解压
    await _pythonDir!.create();
    ...下载并解压...
}
var pythonExePath = .../python/python.exe;  // ← 不存在 → 进程启动失败
```

首次下载失败后会留下**空目录** `build/flutter/build/build_python_<ver>/`；
之后每次构建都因"目录已存在"跳过下载，直接去调用不存在的 `python.exe`，
于是**失败状态会一直自保持**。必须删除该空目录才能恢复。

**第二层：网络**。所需运行时全部来自 GitHub Releases：

| 用途 | 仓库 | 缓存位置（`$FLET_CACHE_DIR` 下） |
|---|---|---|
| 宿主 CPython（交叉编译字节码） | `astral-sh/python-build-standalone` | `python-build-standalone/<date>/` |
| Android 运行时 | `flet-dev/python-build` | `python-build/v<full_version>/` |
| dart-bridge `.so` | `flet-dev/dart-bridge` | `dart-bridge/v<ver>/` |

**决定性证据**：`C:\Windows\System32\drivers\etc\hosts` 第 55–84 行有整段
`127.0.0.1 github.com` / `objects.githubusercontent.com` / `api.github.com` 条目。
时间线对得上：21:03 时 github.com 还通（成功下载 611 KB 模板与 manifest）→
21:52 探测为**超时 20s** → **21:54:19 hosts 被改写** → 之后一律**立即拒绝（0.002s）**。

**来源**：机器上运行着 **Steam++ / Watt Toolkit**（`Steam++.Accelerator.exe`）。
该工具的设计是：写 hosts 把 GitHub 指向 127.0.0.1，再由**它自己的本地反向代理**转发。
实测它的 3 个进程**没有任何监听端口**，`127.0.0.1:443` 也无监听 →
hosts 生效而代理缺席，形成对 GitHub 的全域阻断。

**关键教训**：`github.com` 解析到 `127.0.0.1` 时**不要去归因于防火墙**。
先 `getent hosts github.com` 看一眼，再去查 hosts 文件与访客代理类工具。

**已做的缓解**（全部落在工程内，未越界）：这些工具都支持环境变量覆盖：

| 变量 | 作用 | 依据 |
|---|---|---|
| `FLET_CACHE_DIR` | 缓存根目录 | `package_command.dart:129`、`build.gradle.kts:99` |
| `SERIOUS_PYTHON_DART_BRIDGE_DIST` | 指向本地目录 → **直接跳过** dart-bridge 下载任务 | `build.gradle.kts:399,416` |
| `SERIOUS_PYTHON_BUILD_DIST` | 走 `copyOrUntar` 的 `copyBuildDist` 分支，**取代整个 `packageTasks`** | `build.gradle.kts:445` |

已用镜像 `gh-proxy.com` 预置宿主 CPython 进工程内 `.flet-cache`
（21,980,728 字节，gzip 魔术字节与解压内容均校验通过）。

**踩到的第二个坑：环境变量根本没传下去（失败还是静默的）。**
首次尝试用 `FLET_CACHE_DIR` 时，日志显示仍下载到默认路径 `C:\Users\H\.flet\cache\...`。逐层排查：

- `flet_cli` 传给子进程的是**白名单**（只写 `PATH` / `JAVA_HOME` / `ANDROID_HOME`
  加它自己设的变量），看起来环境变量对用户不可用 —— 但**这个结论是错的**：
  `utils/processes.py:44` 会把 `os.environ.copy()` 合并进去，
  所以**只要变量能进 flet.exe 的环境，就能一路传到 Dart / Flutter / Gradle**
- 真正的原因是 **WSL 不向 Windows 进程传递任意环境变量**。实测 `cmd.exe /C set FOO` 为空；
  必须把变量加进 `WSLENV`。实测结论：

  | 写法 | 结果 |
  |---|---|
  | `VAR=v flet.exe`（不加 WSLENV） | ❌ 静默丢弃，**不报任何错** |
  | `WSLENV="$WSLENV:VAR/w"` | ✅ 成功 |
  | `WSLENV="$WSLENV:VAR"` | ✅ 成功 |
  | `WSLENV="$WSLENV:VAR/u"` | ❌ 方向相反 |

**仍有一个硬限制**：Android 运行时由 Gradle 的 `downloadDistArchive_*` 下载，
带 `onlyIfModified(true)` + `useETag("all")` ——
**即使缓存里已有文件，仍会向 github.com 发条件请求**，连接失败即任务失败。
`SERIOUS_PYTHON_BUILD_DIST` 理论上能跳过它，
但那需要一个 serious_python 自身产出的预编译 dist 目录，无法凭空构造。
因此**必须让 github.com 真正可达**。

#### R20 · 环境 · Windows 未开"开发人员模式"，Flutter 无法创建符号链接 ✅ 已解决

- **现象**：构建推进到 Flutter 阶段后失败：
  `Building with plugins requires symlink support. Please enable Developer Mode in your system settings.`
- **根因**：Flutter 构建带插件的应用时，会在 `.dart_tool` 下为每个插件创建**符号链接**。
  Windows 上创建符号链接需要 `SeCreateSymbolicLinkPrivilege`，普通用户没有该权限
- **无绕过**：`flutter_plugins.dart:1149-1162` 捕获 `ERROR_PRIVILEGE_NOT_HELD (1314)`
  后直接 `throwToolExit` —— 源码中**没有任何降级分支或开关**。
  这与"加个参数就能绕"的 Windows 问题不同，是硬前提
- **实测状态**：注册表 `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock`
  下的 `AllowDevelopmentWithoutDevLicense` **不存在** → 开发人员模式未开启
- **处置**（需管理员权限，因此需用户操作）：
  - 设置 → 系统 → 开发者选项 → 打开「开发人员模式」
    （或 `Win+R` 运行 `start ms-settings:developers`）
  - 等价命令（管理员终端）：`reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock" /t REG_DWORD /f /v AllowDevelopmentWithoutDevLicense /d 1`
  - 备选：从**管理员**终端运行构建（Windows 10 build 14972 之前只有这一条路）
- **结果**：用户已开启。实测注册表 `AllowDevelopmentWithoutDevLicense = 0x1`，
  并用 Windows Python 实际调用 `os.symlink` 验证通过（不只是看注册表）

#### 操作注意 · 终止构建后必须清理残留状态 ⚠️

中途终止构建本身有时必要（如换镜像、换代理），但**终止后会留下自保持的残留状态**，
不清理就会让下一次构建继续失败或空转。本轮踩到的三种：

| 残留物 | 后果 | 清理方式 |
|---|---|---|
| `build/flutter/build/build_python_<ver>/` 空目录 | 跳过运行时下载，调用不存在的 `python.exe` | 删除该目录 |
| `build/.hash/package` stamp | 误判"无变化"，跳过 site-packages 安装 | 删除该 stamp |
| Gradle / Kotlin 守护进程 | 缓存了旧代理设置、持有文件锁 | `Stop-Process` 全部 java 进程 |

另外：**中断 Java 进程后，Gradle 守护进程不会自动退出**，必须显式停止，
否则新构建会复用它（带着旧代理设置，或卡在旧锁上）。

本轮有一次强杀构建，结果 `build_python_<ver>/` 留下空目录，
**使下一次构建又被"跳过下载"逻辑坑了一次**（表现为完全相同的报错复现，
容易被误判为"修复无效"）。**中断下载 = 制造中毒目录**。
若确实需要中断，中断后必须先删除该目录再重试。

#### R21 · 工具缺陷 · flet_cli 在 Windows 上用 `echo y |` 喂 sdkmanager，完全无效 ✅ 已绕开

`utils/android_sdk.py:336` 与 `:372` 在 Windows 分支构造：

```python
["cmd.exe", "/C", "echo", "y", "|", sdkmanager_exe, package_name]
```

- **为什么无效**：`echo y` 只产生**一行** `y`，而 sdkmanager 要逐条询问 7 个许可证；
  实测连第一条都答不上（提示停在 `Review licenses that have not been accepted (y/N)?`）
- **后果**：SDK 目录里只留下一个空壳 `cmdline-tools`，
  而 flet 却打印了 `Android SDK installed OK` —— **报成功但什么都没装上**
- **正确做法**：用**文件重定向**喂 stdin（实测有效）：

```bash
# 先准备多行 y 的文件，再用 < 重定向
printf 'y\n%.0s' {1..200} > .sdk-yes.txt
cmd.exe /C "...\sdkmanager.bat --sdk-root=... --licenses < D:\class_schedule\.sdk-yes.txt"
# → Accept? (y/N): All SDK package licenses accepted
```

- **一次性收益**：许可证文件写入后，后续 AGP 中途拉取 NDK 等组件不再询问。
  实测日志里出现了 `License for package NDK (Side by side) 28.2.13676358 accepted.` —— 
  否则这一步又会被那个失效的 `echo y |` 卡死
- **另一个陷阱**：`_install_package` 即使安装成功也会返回非零退出码，
  导致 flet 误判失败并中止（例：`platform-tools` 实际已安装成功，却抛了
  `Error installing Android SDK tools`）。且因为 `capture_output=False`，
  `p.stderr` 为 `None`，**连错误信息都没有**
- **绕法**：用 argv 列表直接调 sdkmanager（避开包名里分号被 shell 解析），
  或预先装好 `MINIMAL_PACKAGES` 让 flet 逐个跳过（`if home_dir.joinpath(...).exists(): return 0`）

#### R22 · 环境 · Java 不信任 MITM 根证书（PKIX）✅ 已修复

- **现象**：Gradle wrapper 下载失败，堆栈为
  `javax.net.ssl.SSLHandshakeException: PKIX path building failed`
- **为什么不一致**：本机有 SSL 检查（Steam++ 与深信服的根证书在
  **本地计算机\根** 中）。Windows 应用（Python、浏览器）的信任锚是 Windows 证书库，
  所以一切正常；**Java 用自己的 `cacerts`**，不认这个 CA，于是拒绝
- **完整证书链**：`flutter_plugins.dart` 无关，真正的差别在信任锚来源，
  不能因为"Python 能通"就断定 Java 也能通
- **修复**（全部落在工程内）：
  1. 用 PowerShell 从 `Cert:\LocalMachine\Root` 导出所有 `SteamTools|Sangfor` 证书（共 12 张）
  2. 复制 JDK 的 `cacerts` 到工程内 `.java-truststore/cacerts`（保留标准 CA）
  3. `keytool -importcert` 逐张导入
  4. 用 `JAVA_TOOL_OPTIONS=-Djavax.net.ssl.trustStore=...` 指向它（经 `WSLENV` 传递）
- **注意**：`keytool` 的**可执行文件要用 WSL 路径**（`/mnt/c/...`），
  而 **`-keystore` / `-file` 参数要用 Windows 路径**（`D:\...`）—— 混了会报 command not found
- **验证**：日志出现 `Picked up JAVA_TOOL_OPTIONS: ...`，且 PKIX 报错归零

#### R23 · 环境 · Gradle 发行包下载只有 20 KB/s ✅ 已修复（换国内镜像）

- **现象**：`assembleRelease` 卡在下载 `gradle-8.14-all.zip`；
  实测 **11 秒只下 163,840 字节（≈15 KB/s）**，按此速度 230 MB 要 **约 4 小时**
- **关键手法**：**看文件系统而不是看日志**、**看目标文件字节增量而不是看 CPU**。
  日志有缓冲，CPU 低也可能是正常（网络等待的线程 CPU 本就接近 0）
- **测速对比**（这才是决定性的）：

  | 源 | 实测 |
  |---|---|
  | `services.gradle.org`（经 MITM） | 20 KB/s |
  | 腾讯 / 南大镜像 | **12 MB/s** |

- **修复**：改写 `build/flutter/android/gradle/wrapper/gradle-wrapper.properties` 的
  `distributionUrl` 指向腾讯镜像。**实测 8 秒下完 164 MB**，提速约 1000 倍
- **教训**：遇到"下载慢"应先**测速对比**再动手，
  而不是先归因于框架或反复重启

#### R24 · 工具陷阱 · zsh 把 `$VAR:NAME` 里的 `:F` 当成参数修饰符 ✅ 已修复

- **现象**：`WSLENV="$WSLENV:FLET_CACHE_DIR/w:JAVA_TOOL_OPTIONS"` 报
  `zsh: division by zero`，换写法又报 `zsh: bad math expression: ':' without '?'`
- **根因**：`:F` 是 zsh 的合法**参数修饰符**（repeat），于是把 `LET_CACHE_DIR` 当作
  重复次数去求值 → 数学表达式错误。`:G` / `:P` / `:J` 等同理
- **为什么难查**：用 `X` / `Y` 做测试时一切正常（`:X` / `:Y` 不是修饰符），
  极易误判为"随机故障"
- **修复**：**加花括号** `WSLENV="${WSLENV}:..."` 阻断修饰符解析

#### R25 · 工具链缺陷 · Kotlin 增量编译跨盘符抛异常导致构建卡住 ✅ 已修复

- **现象**：构建看起来"卡死" —— CPU 空转（0.6%）、无文件写入、无日志
- **根因**（从 Gradle 守护进程日志挖出）：

  ```
  40 个插件模块都报：Could not close incremental caches in ...\build\<plugin>\kotlin\...
  Suppressed: java.lang.IllegalArgumentException: this and base files have different roots:
      C:\Users\H\AppData\Local\Pub\Cache\hosted\pub.dev\shared_p...
      at kotlin.io.FilesKt__UtilsKt.toRelativeString(Utils.kt:117)
      at ...RelocatableFileToPathConverter.toPath(RelocatableFileToPathConverter.kt:24)
  ```

  Kotlin 增量编译要在"工程目录"（D 盘）与"pub 缓存中的插件源码"（C 盘）之间算相对路径，
  **不同盘符**直接抛异常。这是 Flutter 在 Windows 上把工程与 pub 缓存放在不同盘时的已知问题
- **修复**：`.gradle-home/gradle.properties` 写 `kotlin.incremental=false`。
  **为什么放这里**：`flet build` 每次会改写工程自身的 `gradle.properties`，写那儿会被覆盖
- **教训**：判断"卡住"不能只看 CPU —— 应结合**线程栈**（`jstack`）。
  栈里停在 `SocketInputStream.read` 是**等网络**（CPU 本就近 0），
  停在 `getNextItem` 才是真的没有可执行工作了

#### R26 · 环境 · 编码变量未进 `WSLENV` 导致 rich 向 GBK 控制台写希伯来字母崩溃 ✅ 已修复

- **现象**：构建跑完 Gradle 编译后，报
  `UnicodeEncodeError: 'gbk' codec can't encode character '\u05e2'`，
  崩溃位置在 `rich/_windows_renderer.py → legacy_windows_render → _win32_console.write_text`
- **误导性**：崩溃发生在收尾阶段，**把 Gradle 的真实结果完全掩盖** ——
  日志里只有 Python traceback，没有任何 `BUILD SUCCESSFUL/FAILED`
- **关键实验**（决定性）：

  | 方案 | 结果 |
  |---|---|
  | 不传编码变量（＝当时构建现状） | ❌ `UnicodeEncodeError`，exit≠0 |
  | 经 `WSLENV` 传 `PYTHONUTF8=1` + `PYTHONIOENCODING=utf-8` | ✅ exit=0，正确输出 |

- **根因**：这两个变量**写在了 shell 里但没写进 `WSLENV`，于是被静默丢弃**。
  与 R19 是同一个陷阱，只是当时没把这两个变量一并加进去
- **失败的尝试**：设 `TERM=xterm-256color` 想绕开 `legacy_windows_render` **无效** ——
  实测 `rich.Console().legacy_windows` 在 `TERM` 取任意值时**均为 `True`**

#### R27 · 工具缺陷 · `--skip-site-packages` 的自保持空状态导致 APK 缺依赖 ✅ 已修复

- **现象**：`exit=0`、日志显示 `Successfully built your .apk`，但
  `assets/sitepackages.zip` 只有 **22 字节（一个空 zip 正好是 22 字节，0 个条目）**，
  整个 APK 里**没有任何含 `flet` 的条目**，`stdlib.zip` 里也只有标准库
- **后果**：这个 APK 装到手机上会直接 `ModuleNotFoundError: No module named 'flet'` 崩掉，
  **而构建却报成功** —— 属于最危险的一类问题
- **根因**（`build_base.py` 的哈希判重）：

  ```python
  if not hash.has_changed():
      package_args.append("--skip-site-packages")   # 假定上次已暂存好
  ...
  hash.commit()                                     # 无论是否跳过，都提交 stamp
  ```

  某次运行时哈希恰好"未变" → 跳过安装 → **但 stamp 照样提交** →
  以后每次都"未变" → 永远跳过。**空状态自我保持**，
  与 R19 的"中毒目录"是同一类故障
- **修复**：删除 `build/.hash/package` → `has_changed()` 返回 True → 真正执行安装。
  构建日志出现 `Installing [flet] with pip command to ...`，
  且参数里不再有 `--skip-site-packages`
- **结果**：`sitepackages.zip` 从 **22 字节 / 0 条目** 变为
  **4,903,664 字节 / 564 条目**（含 289 个 `flet` 条目），APK 从 50.4 MB 增至 52.4 MB
- **教训**：**构建报成功 ≠ 产物可用**。拿到 APK 后应验证内部关键组件，
  而不是只看退出码

### 4.5 安装到手机前的检查清单（对应 R13）

- [ ] 设置 → 关于手机 → 连点"版本号"7 次（开开发者模式）
- [ ] 设置 → 系统和更新 → 开发人员选项 → 打开"USB 调试"
- [ ] 设置 → 安全 → **关闭"纯净模式"**（否则侧载安装会被拦截）
- [ ] 确认系统是 HarmonyOS 4.x 而非 NEXT（5.x）——若为 NEXT，APK 路线不可行
- [ ] 安装时允许"外部来源应用"



### 4.6 工程内的 `.venv/`（已启用为开发环境）

- 来源：会话早期执行 `python3 -m venv --copies .venv` 时报
  `'/usr/bin/python3' 与 .../bin/python3 是同一文件`，当时以为创建失败
- 复查真相：**这个 venv 其实是可用的**。NTFS 挂载盘无法复制解释器二进制，
  于是退化为指向系统解释器的符号链接；但 `sys.prefix` 指向 venv 自身、
  `sys.base_prefix` 为 `/usr`，仍是合格的独立环境（site-packages 也在 venv 内）
- 已按用户决定安装 `flet[cli,web]`：`exit=0`，依赖全部解析成功
- 验证：`./.venv/bin/flet --version` → Flet 1.0.0 / Flutter 3.44.8（与旧环境一致）；
  `selfcheck.py` 66 项全过；`check_views.py` 通过；**应用已用该环境成功启动并渲染正常**
- **收益**：开发环境现在位于工程目录内，0.1 节的约束不再存在实际例外
- 与打包无关：`.venv` 位于工程根目录而不在 app path（`src`）下，
  且 `tools/package_android.sh` 已排除它，不会进入 APK
- 遗留项已处置：目录外的 `/home/h/.venvs/class_schedule`（187 MB）**已按用户确认删除**，
  变空的 `~/.venvs` 父目录一并移除；工程内环境不受影响

---

## 5. Flet 1.0 API 要点（实测，避免重复踩坑）

当前环境安装的是 **Flet 1.0.0**，与网上大量 0.2x 教程差异很大：

| 事项 | 正确写法 |
|---|---|
| `ft.ElevatedButton` | **已移除**，用 `ft.Button` / `ft.FilledButton` |
| `ft.NavigationDestination` | 不存在，用 `ft.NavigationBarDestination` |
| 对话框 | `page.dialog` / `page.open()` 已移除，用 `page.show_dialog()` / `page.pop_dialog()` |
| 下拉框事件 | 无 `on_change`，用 `on_select` |
| 下拉选项 | `ft.DropdownOption(key=..., text=...)`，值放在 `key` |
| 事件名 | `page.on_resize`（不是 `on_resized`） |
| 内边距 | `ft.Padding.symmetric(...)`、`ft.Padding.all(...)`（`ft.padding.symmetric` 不存在） |
| 圆角 | `ft.BorderRadius.all(n)` |
| 输入框圆角 | `TextField.border_radius` 已弃用，用 `border=ft.OutlineInputBorder(border_radius=...)` |
| `Control.page` | 未挂载时**抛 RuntimeError**，不能当 `None` 判断；需显式挂载标志 |
| 安装 | `flet` 本体不含 CLI 与 Web 端，需 `pip install "flet[cli,web]"` |
| 中文字体 | 走系统字体，无需额外配置 |

### 5.1 三个非 API 层面的坑（同样是实测踩出来的）

- **开发态的数据目录不在工程根目录**：Flet 会向应用进程注入 `FLET_APP_STORAGE_DATA`，
  开发态指向 `<app_path>/.flet/storage/data`。工具脚本若自行挑选目录（如 `.devdata`），
  就会出现"脚本写了数据、应用读不到"，且现象看起来像渲染故障。见 4.1。
- **本环境下 `flet run` 的热重载不生效**：改动源码后页面仍是旧行为，
  必须**整体重启 `flet run` 进程**才会加载新代码。
  判断依据：新增的日志/输出丝毫没有出现。曾因此把"热重载没生效"误判为"代码没起作用"，
  多绕了一轮排查。
- **主题默认跟随系统，会毁掉硬编码配色的界面**：`Page.theme_mode` 默认
  `ThemeMode.SYSTEM`，系统切到深色时默认文字色变近白，落在白底上等于消失。
  本项目的教训是：硬编码浅色配色就必须显式锁定 `ThemeMode.LIGHT`。见 R14。

### 5.2 排查与验证的三条有效手段

- **不要用 `control.page is None` 判断是否挂载**：Flet 的 `Control.page`
  是沿 parent 链向上查找、找不到就抛 `RuntimeError`；而 `Control.parent`
  始终安全返回 `None`。需要判断挂载时，自己沿 parent 链走（见 `layout.is_on_page`）。
- **用 `inspect.signature` / 读第三方源码取证，而不是凭记忆**：
  `ThemeMode.SYSTEM` 默认值、`Page.add` 的行为、`Control.page` 的抛异常语义，
  都是这样确认的。Flet 版本迭代快，凭记忆写代码会反复踩坑。
- **验证界面交互时优先用无障碍语义树定位元素，而不是靠坐标换算**：Flet Web 渲染在
  canvas 上，截图量像素推算按钮位置**不可靠**（已验证：按坐标点"保存"无效，
  按语义树引用点击则立即生效）。启用方式是在页面里触发 `flt-semantics-placeholder`
  的点击，之后每个控件都会带 `aria-label`，能直接读到按钮名、勾选状态与文本值，
  也能反向核对数据绑定是否正确。

---

## 6. 环境与运行方式

### 6.1 开发环境（当前）

- Python 3.12.3（系统解释器提供 base）
- 虚拟环境：**工程内 `./.venv`**（已装 `flet`、`flet-cli`、`flet-web`，均为 1.0.0）
- 该 venv 的解释器经符号链接指向系统 Python（NTFS 挂载盘无法复制二进制），
  但 `sys.prefix` 指向 venv 自身，属合格独立环境
- 目录外的旧虚拟环境（187 MB）已删除，见 0.2 与 4.6

### 6.2 常用命令

```bash
# 核心层自测（不需要 flet 界面）
./.venv/bin/python tools/selfcheck.py

# 控件树校验（自带内存样本，不依赖磁盘数据）
./.venv/bin/python tools/check_views.py

# 生成演示数据（写入应用实际读取的目录）
./.venv/bin/python tools/seed_demo.py

# 只查看应用当前使用的数据文件路径
./.venv/bin/python tools/seed_demo.py --show

# 启动应用（Web 模式，适合无显示器环境 / 远程开发）
./.venv/bin/flet run --web --port 8550 src

# 启动应用（桌面热重载模式）
./.venv/bin/flet run src

# 核验 APK 产物（每次打包后必做，重点看 sitepackages.zip 里有没有 flet）
./.venv/bin/python build/verify_apk.py

# 打包 APK：用 9.2 里那条完整命令（必须带那一组环境变量）
#   ⚠️ 不要用 tools/package_android.sh —— 它把工程同步到 $HOME/build 再构建，
#      不带 FLET_CACHE_DIR / GRADLE_USER_HOME 等变量，会退化成冷构建（40–60 分钟）；
#      而且它的 BUILD_ROOT 指错时会把工程拷进自己的子目录（见 9.7）
```

### 6.3 数据文件位置

统一由 `core/storage.get_data_dir()` 决定，优先级：

1. **`FLET_APP_STORAGE_DATA` 环境变量**（Flet 为应用进程注入，打包与开发态都会注入）
   - 开发态实测值：`/mnt/d/class_schedule/src/.flet/storage/data/schedule.json`
   - 打包运行：Flet 提供的应用私有目录，随应用卸载一并清除
2. 工程内 `.devdata/`（仅在拿不到环境变量时回退，例如直接运行裸脚本）

**注意**：应用只认第一条。开发脚本必须通过 `storage.use_dev_dir()` 对齐到同一位置，
否则会写进另一份文件而应用读不到 —— 这正是 4.1 踩过的坑。

设置页底部会直接显示当前生效的数据文件绝对路径，便于排查。

---

## 7. 目录结构

```
/mnt/d/class_schedule/
├── PROGRESS.md              本文件：计划、进度、协作约定
├── pyproject.toml           依赖与 [tool.flet] 打包配置
├── .gitignore               忽略构建缓存与开发环境
│
├── 【构建相关目录】均在工程内，均已 gitignore（可再生产，约 1.5 GB）
├── .flet-cache/             FLET_CACHE_DIR：宿主 CPython / Android 运行时 / dart-bridge / 模板
├── .gradle-home/            GRADLE_USER_HOME：Gradle 发行包 + 依赖缓存 + gradle.properties / init.d
├── .java-truststore/        为绕过 MITM 的 PKIX 问题而建的 Java 信任库（含 12 张 CA）
├── build/                   Flutter 工程与构建中间产物；build/apk/ 为最终交付的 APK
│
├── .venv/                   开发虚拟环境（已装 flet[cli,web]；不进入 APK）
├── src/
│   ├── main.py              入口：确定数据目录 → 装载数据 → 搭外壳
│   ├── state.py             AppState：selected_date 唯一真相源 + 变更广播
│   ├── core/                不依赖 flet，可独立测试
│   │   ├── config.py        常量：12 节默认时间表、色板、布局尺寸
│   │   ├── models.py        数据模型 + 序列化 + 脏数据容错
│   │   ├── week_engine.py   周次/日期互推、过滤、车道布局
│   │   └── storage.py       JSON 原子写入
│   └── ui/
│       ├── app_shell.py     底部导航、视图调度、刷新分发
│       ├── layout.py        共用布局工具与课程块渲染（两视图共用）
│       ├── schedule_view.py 周视图
│       ├── day_view.py      单日视图
│       ├── course_form.py   课程新增/编辑表单（含课程级备注）
│       ├── note_form.py     单节课备注弹层
│       ├── week_picker.py   周次多选组件
│       └── settings_view.py 学期设置
└── tools/
    ├── selfcheck.py         核心层自测
    ├── check_views.py       控件树校验
    ├── seed_demo.py         演示数据
    ├── probe_flet_api.py    Flet API 探测
    ├── probe_flet_signatures.py
    └── package_android.sh   打包脚本
```

---

## 8. 关键设计说明

### 8.1 两视图联动为什么用"单一日期真相源"

`selected_date` 是唯一真相源，`current_week` 由它实时推导：

- 周视图翻页 = 日期 ±7 天
- 单日视图翻页 = 日期 ±1 天
- 周视图点某天列 = 直接赋值为该日

三种操作都只改一个字段，因此两视图在**结构上**不可能不同步，无需任何双向同步代码。

### 8.2 为什么两个视图共用 `layout.course_block()`

跨节次课程的高度公式、车道切分公式只在 `layout.block_geometry()` 里实现一份。
只要公式变了，两个视图同时变，不会出现"周视图显示 2 节、单日视图显示 3 节"这类不一致。

### 8.3 为什么不依赖退出钩子保存

Flet 打包后的应用退出时进程会**立即终止**，`atexit`、`__del__`、未 flush 的写入都不保证执行。
因此每次数据变更都立即显式落盘（写临时文件 + `os.replace` 原子替换），
不存在"退出时统一保存"这种机会。

### 8.4 为什么视图是"每次刷新整体重建"

课程数据规模很小（一学期几十门课），重建成本可忽略，
换来的是不存在"数据变了但某个控件忘了同步"这类问题。仅设置页例外
（其中的输入框在编辑过程中不应被重建覆盖）。

### 8.5 翻页动画为什么只能做"单侧滑入"

`refresh()` 会整体重建视图（见 8.4），旧画面在动画开始前就已丢弃，
所以做不出"旧内容滑出 + 新内容滑入"的双画面效果。
可实现的方式只有：让新内容带着一个起始偏移先被渲染，再动画归零。

两个必须注意的点：

- **起始偏移必须先真正渲染出一帧**，否则 Flutter 会把两次变更合并成一次提交，
  起始值永远不会被绘制，动画被静默跳过。所以用 `page.run_task` 延迟
  `PAGE_SLIDE_SETTLE_DELAY`（50ms）再改值，而不是同步改
- **偏移必须裁剪**，否则滑入时网格会溢出到导航栏上
  （外层容器用 `ClipBehavior.HARD_EDGE`）

代价：滑动过程中，旧内容本该在的位置会短暂露出页面背景。
若日后想做真正的双画面滑动，需要把翻页改成"视图内部动画 + 动画结束后再提交状态"，
而不能走 `refresh()` 全量重建这条路。

---

## 9. 打包与真机验证（进行中）

### 9.1 为什么在 Windows 侧构建，而不是 WSL

实测依据：

| 环境 | Python | Flet | PyPI 可达 | 其他障碍 |
|---|---|---|---|---|
| WSL | 3.12.3 | 1.0.0 | ❌ **超时** | 装 JDK 需要 `sudo apt`，提权命令无法非交互执行 |
| Windows | 3.12.10 | ✅ 已装 `flet[cli]` | ✅ **可达** | — |

另外工程本身就在 `D:\class_schedule`，Windows 侧可直达，**不需要**同步到 `~/build/`。

（`tools/package_android.sh` 里的 WSL 同步方案保留，仅供纯 WSL 环境下使用。）

### 9.2 构建命令与当前状态

```bash
# 在工程根目录执行（Windows 侧）。以下每一项都不可省略
cd /mnt/d/class_schedule

# 注意：必须写 ${WSLENV}（带花括号）。写成 $WSLENV:XXX 会被 zsh 当成参数修饰符
# （:F / :G / :P / :J 都是合法修饰符）—— 见 4.4 的 R24
export WSLENV="${WSLENV}:FLET_CACHE_DIR/w:JAVA_TOOL_OPTIONS:GRADLE_USER_HOME/w:PYTHONUTF8:PYTHONIOENCODING:SERIOUS_PYTHON_DART_BRIDGE_DIST/w"
export FLET_CACHE_DIR='D:\class_schedule\.flet-cache'
export JAVA_TOOL_OPTIONS='-Djavax.net.ssl.trustStore=D:\class_schedule\.java-truststore\cacerts -Djavax.net.ssl.trustStorePassword=changeit -Dhttps.proxyHost=127.0.0.1 -Dhttps.proxyPort=7892 -Dhttp.proxyHost=127.0.0.1 -Dhttp.proxyPort=7892'
export GRADLE_USER_HOME='D:\class_schedule\.gradle-home'
export SERIOUS_PYTHON_DART_BRIDGE_DIST='D:\class_schedule\.flet-cache\dart-bridge\v1.9.0'
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

# ⚠️ 日志必须重定向到文件，**不要 `| tail`**：tail 会把根因一起截掉。
#    本轮就因此白跑了两次构建（只看到 BUILD FAILED，根因被丢掉）。
/mnt/c/Users/H/AppData/Local/Programs/Python/Python312/Scripts/flet.exe \
  build apk --yes --no-rich-output -v > build/build.log 2>&1
# 失败时这样看关键片段：
grep -n -i "FAILURE\|What went wrong\|Execution failed\|Caused by" build/build.log | head -30
```

每一项的必要性（按踩坑顺序）：

| 项 | 为何必需 | 依据 |
|---|---|---|
| `--yes` | 从 WSL 调 Windows 交互式 CLI 时 **stdin 喂不进去**，不给会永久卡住 | R17 |
| `--no-rich-output` | 否则 rich 向 GBK 控制台写非 GBK 字符就抛 `UnicodeEncodeError` | R18、R26 |
| `WSLENV` | **WSL 不向 Windows 进程传递任意环境变量，且丢弃是静默的** | R19、R24 |
| `PYTHONUTF8` / `PYTHONIOENCODING` | 必须**经 WSLENV** 才能到达；否则 rich 回显 Gradle 输出时崩溃 | R26 |
| `FLET_CACHE_DIR` | 缓存落到工程内，同时满足约束与镜像预置 | R19 |
| `JAVA_TOOL_OPTIONS` | Java 不认 MITM 根证书，需指向工程内信任库；**并带上代理**（WSL 有 `http_proxy`，Windows 侧 JVM 默认没有，见 9.2.1） | R22 |
| `GRADLE_USER_HOME` | Gradle 缓存/init 脚本/守护进程日志都放工程内 | R23、R25 |
| `SERIOUS_PYTHON_DART_BRIDGE_DIST` | 指向本地 dart-bridge 目录后，插件**根本不注册** `downloadDartBridge_*` 任务，彻底不需要 github（源码里就是 `if (dartBridgeDist == null) dependsOn(...)`） | 9.2.1 |

**前置条件**（不满足会在不同阶段失败）：

- [ ] `github.com` 可达 —— **用本地 dart-bridge 后这一项已不再是硬性要求**，
      仅 Android 运行时的条件请求还可能用到（见 9.2.1）
- [ ] Windows 已开**开发人员模式**（见 R20）
- [ ] Android SDK 已接受许可证，且 `MINIMAL_PACKAGES` 均已安装（见 R21）
- [ ] `.gradle-home/gradle.properties` 中有 `kotlin.incremental=false`（见 R25）
- [ ] `.gradle-home/init.d/` 无遗留干预脚本；若曾改过则会走国内 Maven 镜像
- [ ] `.gradle-home/wrapper/dists/gradle-8.14-all/` 下**原站 URL 哈希目录**已预置完整发行包
      （zip + 解压目录 + `.zip.ok`，见 9.2.2）

构建完成后的成功输出：

```
[00:13:09] Running Gradle task 'assembleRelease'...        62.0s
[00:13:10] ✓ Built build\app\outputs\flutter-apk\app-release.apk (48.1MB)
           Built .apk for Android OK
│ Successfully built your .apk for Android!  Find it in build\apk directory. │
```

状态（2026-09-17 15:02 记录，**build 3 已产出并核验**）：

| 组件 | 状态 |
|---|---|
| Flutter SDK 3.44.8 | ✅ 已装（`C:\Users\H\flutter`，3.3 GB） |
| JDK 17.0.13+11 | ✅ 已装（`C:\Users\H\java`，305 MB） |
| Android SDK | ✅ 已装（`C:\Users\H\Android\sdk`，590 MB，含 NDK 2.1 GB） |
| dart-bridge / Gradle 发行包 | ✅ 已缓存在工程内，**构建不再依赖 github**（见 9.2.1 / 9.2.2） |
| Windows 开发人员模式 | ✅ 已开启（见 R20） |
| 依赖安装 | ✅ `Installing [flet] ...`（见 R27） |
| Gradle 构建 | ✅ `assembleRelease` 耗时 **26 秒**（本地 dart-bridge 生效后） |
| **APK 产物** | ✅ **`build/apk/class_schedule.apk`（50.0 MB，552 个条目，SHA1 `c4306eec…`）** |
| ⚠️ 真机安装 | **未验证通过** —— 用户多次安装后手机仍跑最初版本，见 9.6 |

**单次完整构建耗时参考**：热缓存（Gradle 依赖、NDK、运行时、dart-bridge 均已就位）下
约 **30 秒–2 分钟**；冷启动（首次）约 **40–60 分钟**，其中绝大部分耗在网络下载。

#### 9.2.1 关于 github.com 可达性

**现状（2026-09-17 15:02）：硬依赖已基本消除。**
用本地 dart-bridge 目录后，`downloadDartBridge_*` 任务**不再被注册**，
构建对 github 的硬依赖消失，实测构建从 443 秒降到 **26 秒**。
但仍建议保持加速开启 —— Android 运行时（`downloadDistArchive_*`，
带 ETag 条件请求）可能仍会发请求。

**踩坑记录：为什么会出现"WSL 能连 github、Gradle 却超时"**

- 现象：6 个 `downloadDartBridge_<abi>` 任务失败，
  `HttpHostConnectException: Connect to https://github.com:443 [20.205.243.166] failed: Connection timed out`，
  且在 **24 秒**内快速失败
- 而同一时刻 WSL 里 `curl https://github.com` 返回 **HTTP 200、连接耗时 0.7ms**
- 两边解析到**同一个 IP**，行为却相反 ⇒ 不是 DNS 问题
- 根因：WSL 环境里有 `http_proxy=http://127.0.0.1:7892`，
  **而 Windows 侧的 JVM 默认不走代理**。0.7ms 的连接本身也说明 WSL 走的是本地代理，
  不是真实外网往返
- 处置：`JAVA_TOOL_OPTIONS` 追加
  `-Dhttps.proxyHost=127.0.0.1 -Dhttps.proxyPort=7892`（及 http 同名项）

`dart-bridge` 那一路还有一个更彻底的开关（插件源码
`serious_python_android/android/build.gradle.kts:396-417`）：

```kotlin
val dartBridgeDist = System.getenv("SERIOUS_PYTHON_DART_BRIDGE_DIST")
val bridgeFile = if (dartBridgeDist != null)
    File(dartBridgeDist, "libdart_bridge-android-$abi-py$pythonVersion.so")
...
if (dartBridgeDist == null) dependsOn("downloadDartBridge_$abi")
```

即：**只要该变量指向一个含对应命名 .so 的目录，下载任务就根本不会被注册**。
`.flet-cache/dart-bridge/v1.9.0/` 下已有三个 ABI 的 .so，直接指过去即可。

**排查一台机器是否具备条件**（一条命令）：

```bash
getent hosts github.com    # 正常应返回真实 IP（如 20.205.x.x）；
                           # 若返回 127.0.0.1，就是被 hosts 改写了，构建必定失败
```

若返回 `127.0.0.1`：先检查是不是 Steam++ / Watt Toolkit / SwitchHosts /
FastGithub 之类的代理工具写的（见 4.4 的 R19）。
**正确做法是让该工具真正开启加速**（而不是停在半开状态），
或管理员权限清理 hosts 后 `ipconfig /flushdns`。

#### 9.2.2 Gradle 发行包也会被"重置"（R23 复发，已永久规避）

改 `pyproject.toml`（例如 `build_number`）会让 flet **重新生成 Flutter 工程**，
把 `gradle-wrapper.properties` 的 `distributionUrl` 从腾讯镜像改回 `services.gradle.org`。
wrapper 按 **URL 哈希**找缓存 → 原站哈希目录里没有完整发行包 → 去下载 224 MB，
实测 **46 KB/s**（≈1.3 小时），**443 秒后构建失败**。

- 现象识别：栈里出现 `org.gradle.wrapper.Download.downloadInternal`；
  且 `.gradle-home/wrapper/dists/gradle-8.14-all/` 下多出一个哈希目录，里面只有 `.part`
- **处置（比恢复镜像更稳）**：把已下好的完整发行包（zip + 解压目录 + `.zip.ok` 标记）
  **预置到原站 URL 对应的哈希目录** `c2qonpi39x1mddn7hk5gh9iqj`。
  这样无论 flet 之后把配置改成什么，wrapper 都能命中缓存，**不再依赖镜像也不会复发**
- 处置后构建 56 秒（对比失败那次 443 秒）
- 通用教训：**`pyproject.toml` 一改就可能触发工程重生成，从而重置工程内的构建配置**。
  能放到 `GRADLE_USER_HOME` 或缓存侧的修正，就不要留在会被重写的工程文件里

**重要（已过时，保留作历史）**：第 10 轮那次构建启动之后又修改了 `src/` 与 `pyproject.toml`，
所以当时的结果不作为交付物。
**当前交付物是 build 3**（`build/apk/class_schedule.apk`，SHA1 `c4306eec…`），
见第 17 轮与 9.6。

### 9.3 装到手机

前置检查见 4.5 的清单。两条安装路径：

- **直接拷贝 APK**（当前选定）：把 `build/apk/*.apk` 拷到手机 →
  文件管理器打开 → 允许"外部来源应用"。
  好处是零额外安装；代价是看不到日志。
- **adb**（可选，需装 platform-tools 约 15 MB）：`adb install -r xxx.apk`，
  好处是能用 `adb logcat -s flet.python` 读 Python 侧输出、能验 API level。

### 9.4 `FLET_APP_STORAGE_DATA` 验证结果（对应 R6）✅ 已通过

**实测路径**：`/data/user/0/com.example.class_schedule/files/data/schedule.json`
**持久化**：新增课程 → 强制停止 → 重开，**数据依然在**

三项检查全部通过：

| 检查项 | 期望 | 实测 | 结果 |
|---|---|---|---|
| 应用可运行 | 能启动、渲染、交互 | 正常 | ✅ |
| 数据目录 | 应用私有目录 | `/data/user/0/com.example.class_schedule/files/data` | ✅ |
| 强停后持久化 | 数据不丢 | 数据仍在 | ✅ |

路径不以 `.devdata` 结尾，说明环境变量已被注入、回退分支未触发。

> 为什么当时不能从"能启动"直接推断这两项：`FLET_APP_STORAGE_DATA` 缺失时应用
> **照样能正常运行**，只是数据落在回退目录（`.devdata`）里。
> 属于"功能正常但落点不符预期"的软故障，必须看路径或做强制停止测试才能区分。

参考命令（日后排查用）：

```bash
# 看路径：应用内 设置 → 数据文件
# 或用 adb 看落盘情况
adb shell run-as com.example.class_schedule ls -l files/data/
# 可选：确认 API level（不阻塞安装）
adb shell getprop ro.build.version.sdk
```

---

### 9.5 APK 的分发：作为 GitHub Release 附件

**APK 不进版本库**（`.gitignore` 里 `build/` 已整目录排除），改为作为 **Release 附件**
上传。原因：APK 有 50 MB，且每次重建都会生成全新 blob（即使源码只改一行），
git 会永久保留每个版本，仓库会迅速膨胀。

**当前版本号**：`pyproject.toml` 的 `version = "0.1.0"` / `build_version = "0.1.0"`
/ `build_number = 1` → 对应 tag 建议 `v0.1.0`。
`org = "com.example"` + `name = "class_schedule"` → 包名 `com.example.class_schedule`。

**方式一：用 `gh` CLI**

```bash
# 先在 GitHub 建好仓库并关联 remote
git remote add origin git@github.com:<你的账号>/class_schedule.git
git push -u origin master

# 创建带附件的 release
gh release create v0.1.0 \
  build/apk/class_schedule.apk \
  build/apk/class_schedule.apk.sha1 \
  --title "v0.1.0 · 首个可运行版本" \
  --notes "HarmonyOS 4.3.0 真机验证可运行。如需自行构建，见 PROGRESS.md 第 9 节。"
```

**方式二：网页上传**（更简单，且不受本机网络限制）

GitHub 仓库页 → Releases → Draft a new release → 填 tag `v0.1.0` →
把 `D:\class_schedule\build\apk\class_schedule.apk` 拖进附件区 → Publish。

**⚠️ 本机网络注意事项（2026-09-17 15:00 复核，与早期记录不同）**：
hosts 里**已无 github 条目**（`grep -c github /mnt/c/Windows/System32/drivers/etc/hosts` → 0），
`getent hosts github.com` 返回真实 IP（20.205.243.166）。
WSL 侧经 `http_proxy=127.0.0.1:7892` 可正常访问 github（实测 HTTP 200）。
**但 Windows 侧的 JVM 默认不走代理** —— 那是构建时的坑（见 9.2.1），与上传无关。
上传仍建议用**方式二（浏览器）**：WSL 里没有 `gh` CLI。

**为什么 `.sha1` 也一起上传**：它是 APK 的校验值，下载后可核对完整性。
两个文件都应该随 release 走，而不是进版本库。

### 9.6 ⚠️ 真机安装疑似无效（未解决）

**症状**：用户把新构建的 APK 装到手机后，应用行为仍是最初版本的特征
（没有版本号显示、单日里单击课程块弹的是「编辑课程」而不是「本节课备注」、
没有翻页动画）。**卸载后重装也一样。**

**为什么这必然是安装环节的问题**：一次全新安装不可能装出旧代码 ——
包里的 Python 代码是全新的（已核验 `assets/app.zip` 内含 `ui/note_form.pyc`，
且能从 `core/config.pyc` 读出 `0.1.0`、从 `ui/settings_view.pyc` 读出 `版本`）。

**已排除的可能**

- ~~APK 内容不对~~：逐项核验通过（见第 17 轮）
- ~~打包用错了源码~~：构建日志显示 `Copying Python app from D:\class_schedule\src` ✅
- ~~插件复用旧解压结果~~：读 `serious_python_android` 源码，它用
  `versionName+versionCode+lastUpdateTime` 做键，**`lastUpdateTime` 每次重装都变**，
  所以重装必然重新解压 `app.zip`；插件注释里还专门说明了为什么不能用单纯的 versionCode

**剩余嫌疑**：传输环节留了同名旧副本，或从 GitHub Release 下载了旧附件
（**Release 上的附件至今仍是第 10 轮那一版**）。

**已加入的可判定锚点**：设置页显示版本号（build 3 在**页面最顶部**），
装后一眼就能确认装的是哪一版；另一个零成本判定是单击课程块看弹哪个标题。

**教训（写给自己）**：我曾据"APK 内容正确 + 插件会重新解压"就断定
"新代码已在手机上运行"，**这个结论是错的**。
**核验 APK 内容必要但不充分** —— 我从没验证过设备上装的是什么。

### 9.7 ✅ 已清理：工程内曾出现多层嵌套的自身副本

（2026-09-17 15:30 清理完成，共回收 **11 GB**）

**实际深度是 7 层，不是 3 层。** 删除时 Windows 报出的路径是：

```
D:\class_schedule\class_schedule\…\class_schedule\.gradle-home\caches\8.14\transforms
   （共 7 个 class_schedule）
```

原因：`rsync` 没排除 `.git` / `.gradle-home` / `.flet-cache`，
而它又把**上一次已经嵌套进来的副本**一起复制 —— 每跑一次就多一层并翻倍体积，
所以从"三层"迅速长到七层、**11 GB**。
原始目录时间 13:52–13:55，在护栏加入（14:00）之前。

**危害**：副本里有 `src/` 与 `pyproject.toml`。
**若从那一层构建或运行，跑的就是 13:52 的旧代码** ——
这类"改了代码却没生效"极其难排查。

**清理过程踩到的坑（值得记住）**

1. **WSL 的 `rm -rf` 删不掉最深的一层**：报
   `rm: cannot remove '…transforms': Directory not empty`。
   这是 DrvFs 上 **Windows `MAX_PATH`(260 字符) 限制**的典型症状 —— 不是权限问题，
   路径太长时 `rm` 无法枚举/删除里面的文件。
2. **Windows 原生 `rmdir /s /q` 也失败**（同样报"目录不是空的"），
   但 `cmd` 的退出码仍是 0 —— **别信这个退出码**。
3. **最终奏效的办法：逐级把内层目录"提升"到顶层并改成短名**，路径长度骤降后再删：

   ```bash
   n=0; cur=class_schedule
   while [ -d "$cur" ] && [ -d "$cur/class_schedule" ]; do
     n=$((n+1))
     mv "$cur/class_schedule" "short$n" && rmdir "$cur" 2>/dev/null
     cur="short$n"
   done
   for d in short*; do rm -rf "$d"; done
   ```

   提升 5 层后 `rm -rf` 成功。
   **通用结论：DrvFs 上遇到"删不掉的深目录"，先想办法缩短路径，而不是反复重试删除。**

**已加的护栏**（14:00 实测通过）：`TARGET_DIR` 先 `realpath -m` 归一化 →
与源目录相同则拒绝 → **两个方向的包含关系分别拒绝**
（构建目录在源目录内 = 自我递归；源目录在构建目录内 = `rm -rf` 会连工程一起删）。
注意：**第一版护栏把方向写反了**，是跑测试才发现的 —— 没测过的护栏比没有更危险。

**清理结果**：根目录已无 `class_schedule/`，全工程只有一个 `PROGRESS.md`；
66 项自测与控件树校验均通过；`build/apk/` 下的产物未受影响。

**教训（归入"从部分证据推出完整结论"这一类）**

- 我先据目录层级判定"三层"，**实际是七层**
- 我又据 `get_terminal_output` 的一份**截断快照**判定"第一次清理没跑完"，
  实际它跑完了（只是我看不到后面的输出）
- 同类错误本轮已发生三次：
  ① "APK 内容正确 ⇒ 手机上就是新代码"（错）
  ② 用 `| tail` 截断构建输出 ⇒ 看不到根因，白跑两次
  ③ 从截断的终端快照 ⇒ 误判命令未执行
- **共同点：把"我能看到的片段"当成了"事实的全部"。**

## 10. 变更记录

按时间顺序记录每一轮做了什么。保留这份记录是为了能追溯
"某个结论是哪一轮、基于什么证据得出的"，避免日后反复推翻同一判断。

### 第 1 轮 · 立项与技术选型

- 对比 4 条技术路线（Flet / Kivy+Buildozer / PySide6 / Briefcase），
  依据官方文档核实工具链成熟度、中文支持与打包可靠性
- 关键发现：`pyside6-android-deploy` 内部就是调用 buildozer，
  选 Qt 并非绕开 Kivy 的构建风险而是叠加风险
- 选定 **Flet**，产出完整实施计划

### 第 2 轮 · 实现与首次验证

- 写出全部源码（约 1900 行）与开发辅助脚本（自测、控件树校验、演示数据、API 探针、打包脚本）
- 核心层 `tools/selfcheck.py` **66 项断言全过**，含遍历学期 140 天的两视图一致性交叉校验
- 定位"课程块未渲染"：**根因不是渲染失败，而是开发脚本与应用读写的数据文件不是同一份**（详见 4.1）。
  当时对 `StoragePaths` 的怀疑被实测推翻
- 记录 Flet 1.0 与网上 0.2x 教程的大量 API 差异（详见第 5 节）

### 第 3 轮 · 风险检查与修补

- 系统扫描出 R1–R13，每项都附代码位置佐证，而不是泛泛而谈
- 修复：R1（`Control.page` 探测写法会抛异常）、R2（落盘失败无任何提示）、
  R3/R4（打包排除项失效）、R7（校验脚本无数据时误报失败）
- 新增并修复：R14（主题跟随系统导致文字几乎不可见）、
  R15（表单尺寸硬编码被矮视口裁切）、R16（只读展示路径产生目录副作用）
- 界面实测通过：编辑课程、删除课程（含二次确认弹层）、周次多选的数据绑定

### 第 4 轮 · 环境归位与收尾

- 开发环境迁入工程内 `./.venv`；删除目录外的 `/home/h/.venvs/class_schedule`（187 MB）
- **至此 0.1 节的目录约束不再有任何例外**
- 修复 R5（Python 版本偏差）、R8（窄列字号自适应）、R10（旋转丢输入）、R11（路径推导静默失效）
- 评估并定下 R9 / R12 / R13 的处置方式（详见 4.4）
- 记录打包链路的三个坑（详见 4.4 的 R17）
- 启动 Windows 侧 APK 构建（进行中，详见第 9 节）

### 第 5 轮 · 打包链路排障

- 首次 `flet build apk --yes` 退出码 1，但排查发现**工具链其实已全部装好**
  （JDK 17.0.13+11 305 MB、Android SDK 147 MB），失败点与构建步骤无关
- 从崩溃前最后一条成功日志 "Created app shell" 判断：Flutter 工程已生成，属"临门一脚"失败
- 定位 **R18**：rich 向 GBK 控制台打印 ✅ 抛 `UnicodeEncodeError`；
  被 `Live.__exit__` 的二次异常覆盖，日志末尾极具误导性
- 依据 `flet build --help` 中的 `--no-rich-output`
  （文档标注 *"Useful on Windows builds"*）修复，**确认通过**：
  日志出现 `Created app shell OK` 并继续进入 `Packaging Python app...`
- 教训：遇到 Windows 侧 Python CLI 报编码错误，优先查"是否在往控制台打非 GBK 字符"，
  而不是去改应用代码

### 第 6 轮 · 定位 GitHub 阻断根因

- `--no-rich-output` 修好编码问题后，构建推进到 `Packaging Python app...` 又失败，
  报错 `Flet app package was not staged to build\python-app.`（信息量极低的报错）
- 用 `-v` 抓取被 `capture_output` 吞掉的 Dart 输出，发现真正失败点是
  `python.exe -m compileall -b <临时目录>` 启动失败
- 查到 `serious_python` 源码：`build_python_<ver>/` 目录存在就**整体跳过下载**，
  而该目录因首次下载失败而留空 → **失败状态自保持**（已删除该目录）
- 依次排查网络：三个可用镜像
  （`gh-proxy.com` / `ghproxy.net` / `ghfast.top`）已预置宿主 CPython 进工程内缓存
- **最后挖到真正的根因**：`getent hosts github.com` → `127.0.0.1`，
  顺蔓摸到 Windows hosts 文件的整段 Github 封锁条目；
  结合时间线与进程排查，定位到 **Steam++ / Watt Toolkit 半开状态**
  （写了 hosts 但本地代理未运行），详见 4.4 的 R19
- 教训：**报错文案不一定是根因**。这次经历了"报错说 staging 失败 → 其实是子进程启动失败
  → 其实是运行时文件缺失 → 其实是缓存中毒 → 其实是 DNS 被改 "共四层。
  每层都只能靠读源码 + 实测推翻上一层假设

### 第 7 轮 · 打通构建链路（越过打包阶段）

- 用户开启 Steam++ 网络加速后，Windows 侧 `github.com` 与 releases 资源均 HTTP 200
- 顺带纠正一个测试方法错误：**在 WSL 里 `127.0.0.1` 指 WSL 自己的 loopback**，
  不能用来判断 Windows 侧服务；而构建跑在 Windows 侧，必须用 Windows 侧命令测
- 顺带查明 Steam++ 在做 MITM 解密，导致 schannel（`curl.exe`）报
  `CRYPT_E_NO_REVOCATION_CHECK`，但 Dart 的 BoringSSL 与 Java 的 `cacerts`
  都不做吊销检查，**不影响构建**
- 验证 `WSLENV` 方案生效：日志只有 `Extracting Python distributive` 而无 `Downloading`，
  说明命中了工程内预置缓存，省下 21 MB 下载
- 越过 `Packaged Python app OK`（此前一直卡在这里）→ `Got dependencies!`
- 新阻碍 **R20**：Windows 未开开发人员模式，Flutter 建插件符号链接被拒
- 教训：下载/解压阶段**不能强杀**，否则会自己制造中毒目录（见 4.4 操作注意）

### 第 8 轮 · 打通 Gradle：从"卡住"到编译成功

- 用户开启开发人员模式后，越过插件符号链接阶段（R20）
- 遇到 **Java PKIX**（R22）：定位到 Steam++ 与深信服的 MITM 根证书不在 JDK 的
  `cacerts` 里；导出 12 张证书建工程内信任库解决
- 遇到 **SDK 环节报成功但实际什么都没装**（R21）：发现是 flet_cli 的
  `echo y |` 缺陷；改用文件重定向接受许可证，并补装 `MINIMAL_PACKAGES`
- 遇到 **Gradle 发行包 20 KB/s**（R23）：实测腾讯镜像 12 MB/s，换镜像后
  8 秒下完 164 MB
- 遇到 **zsh 修饰符陷阱**（R24）：`WSLENV="$WSLENV:FLET_CACHE_DIR..."` 里的 `:F`
  被当成参数修饰符，报 `division by zero`；改用 `${WSLENV}` 修好
- 遇到 **构建卡住**（R25）：先用 CPU 采样误判为死锁，后来用 **`jstack` 看线程栈**
  才分清"等网络"（`SocketInputStream.read`）与"无工作可做"（`getNextItem`）；
  真正的卡死是 Kotlin 增量编译跨盘符异常，关闭增量编译解决

### 第 9 轮 · 首次成功产出 APK（但有缺陷）

- `exit=0`，`Successfully built your .apk for Android!`，
  `build/apk/class_schedule.apk` 50.4 MB
- 但主动核验产物时发现 **`assets/sitepackages.zip` 只有 22 字节（空 zip）**
- 顺带修掉 **R26**：编码变量未进 `WSLENV` 导致 rich 回显 Gradle 输出时
  因希伯来字母 `\u05e2` 抛 GBK 编码错，且该崩溃**掩盖了 Gradle 的真实结果**

### 第 10 轮 · 补齐依赖，产出可用 APK

- 定位 **R27**：`build_base.py` 的哈希判重加上无条件 `hash.commit()`，
  形成了"跳过 site-packages 安装"的**自保持空状态**
- 删除 `build/.hash/package` 强制重新安装，日志出现
  `Installing [flet] with pip command to ...`
- **最终产物**：`build/apk/class_schedule.apk` = 52,426,472 字节，552 个条目
  - `assets/sitepackages.zip`：22 B / 0 条目 → **4,903,664 B / 564 条目**（289 个 flet）
  - `assets/app.zip` 含 `main.pyc` / `state.pyc` / `core/*.pyc` / `ui/*.pyc`
- 待办：真机安装验证（见 4.5 清单与 9.4）

### 第 11 轮 · 真机验证通过

- 用户把 `build/apk/class_schedule.apk` 装到手机，**应用可正常运行** ✅
- 这一条同时反证了两件事：
  - **R27 的修复是必要且有效的** —— 若 `flet` 未打进 `sitepackages.zip`，
    应用启动就会 `ModuleNotFoundError` 直接闪退
  - Python 运行时（`libpython3.12.so`）、dart-bridge 与 Android 运行时
    （`python-android-dart-3.12.14-arm64-v8a.tar.gz`）三者版本匹配正确，
    否则 native 库加载会失败
- 仍建议顺手确认（不阻塞交付）：设置页"数据文件"路径、
  以及"强停后课程是否还在" —— 详见 9.4 的说明
- **后续补充验证（同日完成）**：
  - 数据文件路径 = `/data/user/0/com.example.class_schedule/files/data/schedule.json`
    → 应用私有目录，`FLET_APP_STORAGE_DATA` 注入成功
  - **强制停止后数据依然在** → 即时保存策略有效
  - 至此 **R6 也已关闭，R1–R27 全部关闭，无待验证项**
- **项目达成原始目标**：能在 HarmonyOS 4.3.0 运行的课程表工具

### 第 12 轮 · 收尾清理

- 删除临时文件：`.build.log`、`.build-help.txt`、`.win-check.txt`、
  `.sdk-yes.txt`、`.sdk-install.py`、`.export-ca.ps1`、`.jstack.txt`
- 新增 `.gitignore`，把构建缓存（`.gradle-home/` 约 1.1 GB、`.flet-cache/`、
  `.java-truststore/`）与开发环境排除在版本库外，
  避免 `git add .` 时误提交 1.5 GB 可再生产物
- **`build/` 做了分层处理**：其中绝大部分是可再生产的中间产物（Flutter 工程、
  Gradle 输出、`.dart_tool` 等）应排除；但 `build/apk/` 下的 APK 是**最终交付物**，
  需要纳入版本管理。规则写成：
  `build/*` → `!build/apk/` → `build/apk/*` → `!build/apk/*.apk`
- **踩到一个 gitignore 语义坑**：**不能"排除整个目录后再把里面的文件加回来"** ——
  父目录被排除时，子路径的 `!` 规则不生效。所以必须排除 `build/*`（内容）
  而不是 `build/`（目录本身）
- **踩到一个隐蔽的 gitignore 坑**：把注释写在模式同行
  （`.gradle-home/    # 说明`）会让规则**静默失效** ——
  gitignore 不支持行尾注释，`#` 之后的内容会被当成模式的一部分。
  它不报错、只是不生效，只能用 `git check-ignore -v <path>` 才能发现
- **另一个容易踩的确认陷阱**：`git check-ignore` 对**否定模式**的退出码语义有歧义
  （匹配到 `!` 行时也会打印并返回 0），容易被误读成"仍被忽略"。
  **权威做法是用 `git ls-files --others --exclude-standard`**
  列出"会被提交的未跟踪文件"，看目标是否在其中
- **最终决定：APK 不进版本库**，改为作为 GitHub Release 附件分发（见 9.5）。
  `.gitignore` 里 `build/` 整目录排除，版本库只留源码与文档
- 最终未忽略的未跟踪文件共 **24 个**：`.gitignore`、`PROGRESS.md`、`pyproject.toml`、
  `src/**`（15 个）、`tools/**`（6 个）

### 第 13 轮 · 课程块字号调大两号

- 用户要求"课程字体调大两号"，`layout.py` 中课块内**所有**字号统一 +2：
  课名 8/9/10 → 10/11/12（按列宽分档）、单日视图 12 → 14、
  周视图地点 8 → 10、单日详情与节次 10 → 12
- **实测验证**（浏览器 390×844，真机尺寸）：
  - 单日视图：层次清晰、无截断 ✅
  - 周视图：4 字课名不再单行显示，折行但**不丢字**
- **发现的空间硬约束**：手机上周视图每列仅 45.1px，文字可用宽 37px，
  而 4 个汉字单行需字号 ≤ 9.25px。**因此只要 >9px 就必然折行**，
  与具体取值无关，调参绕不过去 —— 详见 4.3 的 R8
- **用户选定方案 A**：接受折行，保留大字号（真机可读性优先）
- 教训：窄列 + 大字是硬碰硬的空间冲突，应当先算出断点（9.25px）再决定，
  而不是反复试参数

### 第 14 轮 · 周次切换的滑动动画

- 需求：切换周次时增加滚动动画
- 实现：`AppState` 增加**一次性**的 `_pending_slide`（由 `shift_weeks()` 写入、
  视图 `take_slide()` 取走即清零）；周视图据此把新网格以 `offset=±1` 起始渲染，
  再用 `animate_offset` 归零。方向取自 `_pending_slide`，所以向左滑与向右滑
  新内容从不同侧滑入
- 参数放在 `config.py`：`PAGE_SLIDE_MS = 260`、`PAGE_SLIDE_SETTLE_DELAY = 0.05`
- **验证方式**（动画无法靠单张截图判断，这个方法很有效）：
  1. 在**一次** Playwright 调用内派发点击 + 按 35ms 间隔连续截图，比较各帧指纹
     → 得到 3 个不同指纹，**确认确实渲染了中间态**（而非直接跳变）
  2. 另存一张中间帧图片目视确认：网格处于右偏移、左侧露出背景，
     而导航栏/表头/底部标签位置正常
  3. 语义树确认已翻到第 2 周（`第 2 周（共 20 周）`、`9月21日 - 9月27日 · 未到`）
- 踩到的交互坑：`page.mouse.click` 与 `page.mouse` 拖拽**都到不了 Flutter 画布**；
  而语义节点的 `click` 会被其他语义节点拦截（`intercepts pointer events`）。
  **可行做法是 `locator.dispatchEvent('click')`** 直接派发事件绕过命中测试
- 回归：66 项核心自测 + 控件树校验均通过
- 已知取舍：滑动过程中旧内容位置会短暂露出背景，原因见 8.5

### 第 15 轮 · 两级备注（课程级 + 单节课）

- 需求：单日视图增加备注；创建课程时可输入，单日视图单击可编辑；
  **创建时输入的作用于该课程的所有上课时间，单日视图里编辑的只作用于这一节课**
- 两个关键决策（已与用户确认）：
  1. 两条备注的关系是**并存**而非覆盖 —— 课程级是"这门课的通用说明"，
     单节级是"这次课的临时补充"，两者在课块上各带标记分行显示
  2. 交互分工：**单击课块 = 改本节备注，长按课块 = 改课程**
     （单击是高频动作，长按是低频动作。周视图保持原样：单击 = 改课程）
- 核心层（不依赖 flet，可独立验证）：
  - `Course.note`（课程级）；`ScheduleData.notes`（单节级，键 `"YYYY-MM-DD|course_id"`）
  - 删课程时顺手清掉它名下的单节备注；`normalize()` 再兜一层：
    丢空值、丢课程已不存在的孤儿键 —— 否则文件里会积一堆永不失效的垃圾
  - `config.py`：`NOTE_MARK_COURSE="课程"`、`NOTE_MARK_SESSION="本节"`、`MAX_NOTE_LENGTH=200`
- UI 层：
  - `ui/note_form.py`（新）：弹层顺便把课程级备注只读展示出来，
    让用户看清"哪些是这门课本来就带的、哪些是我这次加的"
  - `ui/course_form.py`：新增「课程备注」多行输入（`_FORM_MAX_HEIGHT` 430→470）
  - `ui/day_view.py`：`notes=(course.note, session_note)`，单击/长按分别接线
- **课块行数预算**（这是本轮最容易被忽略的坑）：
  课块高度固定（由节次决定）、字号又大（第 13 轮刚调到 14pt），
  备注是第一个"行数不确定"的内容。若不预算行数，内容会溢出容器，
  字被静默裁掉、看起来像渲染坏了。做法：
  - 用 `estimated_lines()` 估算课名会占几行（CJK 按全角、西文 0.55 倍字号）
  - 剩余空间按 12pt×1.3 逐行扣，得出还能放几行
  - 候选行按重要性排序：摘要 → 备注 → 节次范围
    （节次范围排最后，因为课块位置与高度本身已经表达了节次）
  - 单节块（60px 高）只放得下 2 行次要信息，两条备注会被合并成
    `课程 … / 本节 …` 一行（仍有标记区分）；放得下就各占一行
- **备注挪进块内右侧的空白列**（看到实际渲染后补做）：
  单日视图在大屏上课块很宽（632px 窗口下单日块宽 542px），
  而课名 + 地点只占左侧约 120px，**右侧一大片纯色空白**。
  于是块宽 ≥ `_SPLIT_MIN_WIDTH`(380) 时改两列：左列 课名/地点教师/节次范围，右列 备注。
  额外收益：备注不再和课名抢垂直空间，**单节块（60px 高）也能把两条备注分开显示**，
  不必再合并成一行 —— 上面那套行数取舍只在大屏以下才用得上。
  窄块（手机竖屏 302px、周视图）仍走纵向堆叠 + 行数预算
- 验证：
  - 核心层 7 项：strip、键格式、往返、传空删键、删课连带清理、normalize 清孤儿、超长截断
  - 行数预算 8 种组合（1/2/4 节 × 有/无备注 × 长课名折行）：估高全部 ≤ 容器高
  - 控件树校验新增两项：两条备注文案都要出现在课块里；
    所有单日课块都必须接上 `on_long_press`
  - 控件树校验再加一项：宽屏（760px）下**所有**课块都得是两列布局，
    防止以后改布局时悄悄退回"备注堆在课名下面"
  - 浏览器实测矩阵（每次读落盘 JSON 复核）：仅课程备注 / 仅单节备注 /
    两条并存（标记与顺序正确）/ 清空课程备注只掉对应那一行 /
    保存课程表单不会冲掉单节备注 / 跨服务器重启+刷新仍在
- 教训（写下来避免重复踩）：
  - **Flutter Web 的输入框用 Playwright `fill()` 注入值不可靠**：
    DOM 的 `<textarea>` 值与 Flutter 内部编辑态会脱钩（表现为
    `max_length` 计数与刚输入的内容对不上，偶发保存成空）。
    要模拟输入必须用 `page.keyboard.type()` 发真实按键事件
  - 同因：未聚焦的 Flutter 文本框在 DOM 里 `value` 是空的，
    真实值只画在画布上。**判断输入框内容要看 `max_length` 计数，不要看 DOM value**
  - `flet run <app_path>` 会把 `FLET_APP_STORAGE_DATA` 指到
    `<app_path>/.flet/storage/data`，即 `src/.flet/...`。
    这个目录是运行时数据（会随使用变化），已加入 `.gitignore`
  - 长按在 Flet Web 的语义树里**没有独立的 DOM 触发点**，
    自动化点不到；只能靠结构断言确保 `on_long_press` 接上了

### 第 16 轮 · 全文件安全审计（重点看"到安卓上会造成严重后果"的问题）

方法论：把 `src/` 全部读完，再对数据层做**破坏性输入注入**
（畸形 JSON、错类型字段、极端数值），最后核对 Android 构建产物清单与签名配置。
只看代码"读起来对不对"查不出这类问题 —— 下面每一条都有实测结果支撑。

#### 已修复（按严重程度排序）

| # | 问题 | 后果（安卓端） | 根因 | 处置 |
|---|---|---|---|---|
| **A1** | 数据文件是**合法 JSON 但字段类型错**时 `from_dict` 抛异常 | **应用每次启动都崩在同一处**，用户从界面里无法自救，只能清空应用数据 = 丢掉整个课表 | `load()` 只把 `json.loads` 包在 try 里，`from_dict` 在 try 外 | `load()` 兜住一切异常；坏文件改名 `.corrupt` 留档，并**把原因报到界面** |
| A1 的 5 个具体触发点（实测全部会崩） | | | | |
| | `{"courses": 123}` | | `(data.get("courses") or [])` 是数字，`for` 迭代抛 TypeError | 新增 `_as_list()`：只接受 list/tuple |
| | `{"notes": "abc"}` | | `dict("abc")` 抛 ValueError | 新增 `_as_dict()`：只接受 dict |
| | `{"settings": {"slot_times": 123}}` | | 同上（`list(123)`） | 同上 |
| | `{"settings": {"total_weeks": Infinity}}` | | JSON 规范禁止 Infinity，但 **Python 的 json 默认接受**；`int(inf)` 抛 OverflowError | `_as_int()` 补接 OverflowError |
| **A2** | 结构损坏时"平静地"读成空课表 | 用户看不到任何异常，课表却空了（静默数据丢失） | `from_dict` 对错类型只是回退成空值 | 新增 `_damage_reason()`：顶层/`courses`/`settings`/`notes` 形状不对就按损坏处理（隔离 + 告知）。本应用写出的文件永远满足该形状，不会误伤正常数据 |
| **A3** | 非法颜色字符串直接交给 Flutter | 课块变透明或渲染报错，用户"看不见课程"且极难排查 | `Course.color` 只判空、不校验格式 | 正则限定 `#RGB/#RRGGBB/#AARRGGBB`，不合规回退默认色 |
| **A4** | 异常只打到控制台 | 手机上表现为"点了没反应"，用户既不能自救也不能反馈 | 未设置 `page.on_error` | 设 `page.on_error` 把异常变成界面上可见的一行提示；带**次数预算**（3 次）防止"报错处理本身报错"造成无限递归 |
| **A5** | `parse_weeks("1-999999999")` 展开上亿个值 | 界面卡死 20 秒 → 安卓直接 **ANR**（系统可能杀进程） | `range(low, high+1)` 未夹紧 | 先夹到 `max_weeks` 再展开。实测 19.9s → 0.0000s |
| **A6** | 减少"每天节数"会**就地压扁课程**且立即落盘 | 12 节改 4 节后，第 5–12 节的课被压到第 4 节，**改回来也恢复不了**（实测：`物理实验 第9-11节 → 第4-4节`） | `Course.normalize` 把 `end_slot` 夹到 `slots_per_day`，而设置页直接保存 | 保存前统计 `end_slot > 新节数` 的课，非空则弹确认框：按超出程度**倒序**列出受影响课程与节次，明确写“永久丢失”“改回来也恢复不了”，操作是「取消 / 仍要保存」（红色）。取消时给提示并让表单回到已保存值，避免“看着像已经改了” —— 否则用户会以为设置生效了 |

A5 目前**没有 UI 入口**（`parse_weeks` 只被工具脚本调用），属潜在问题；
但它是"以后加个周次文本框输入就立刻变成线上事故"的类型，所以一并修掉。

A6 的验证（浏览器端到端，每次回读落盘 JSON）：
- 把每天节数改成 4 → 弹层出现，列出 `物理实验（第9-11节）、体育（第9-10节）、数据结构（第5-6节） 等共 5 门`
- 点「取消」→ 数据零改动（每天节数仍 12、物理实验仍第 9-11 节），并提示"已取消，学期设置未改动"、表单回到 12 行
- 点「仍要保存」→ 确实落盘为 4 节，5 门课的节次被压到第 4 节（证实了警告里说的不可逆损失）

#### 未修（需要你决策，不是纯技术问题）

| # | 观察 | 影响 | 建议 |
|---|---|---|---|
| B1 | **release 包用 debug 签名**（`build.gradle.kts`：`signingConfig = signingConfigs.getByName("debug")`，Flet 模板行为） | 调试密钥是公开的（别名 `androiddebugkey` / 口令 `android`），任何人都能用同一 `applicationId` 签一个"同名更新"覆盖安装；同时无法上架，将来换正式签名必须**卸载重装 = 数据丢失** | 分发前生成正式 keystore，用 `flet build apk --android-signing-key-store ...` 指定 |
| B2 | 权限里带 `INTERNET` + `ACCESS_NETWORK_STATE` | 纯离线课程表声明联网权限，观感与隐私审查都不友好 | 是 Flet 模板/默认插件的产物；**不建议贸然删** —— Flet 内嵌运行时走 localhost socket，删 INTERNET 有让应用起不来的风险，需真机验证后再动 |
| B3 | Flet 默认打包了 **16 个用不到的插件**（battery_plus、connectivity_plus、sensors_plus、screen_brightness、wakelock_plus、share_plus、file_picker、url_launcher、pasteboard、device_info_plus、package_info_plus…） | APK 体积、权限与攻击面都被放大（`ACCESS_NETWORK_STATE` 就来自 connectivity_plus） | 可选优化；要裁剪得改 Flet 的 Flutter 模板（`pubspec.yaml` 由模板生成，旁边有 `.orig`） |
| B4 | 未设 `android:allowBackup`（默认 true） | 课表会被 Android 自动备份上传到用户云备份 | 多数用户希望如此；若要求"数据只留本机"，需自定义清单设 `false` |
| B6 | `get_data_dir()` 在目录建不出来时**静默**切到临时目录并一直用下去 | 用户会以为课表没了，且之后所有保存都写到临时目录 | 触发条件苛刻（安卓应用私有目录建不出来），但应改成"切换的同时给提示" |
| B7 | `save()` 落盘后未 fsync 目录 | 仅断电场景下 rename 可能未持久化 | 低危；要极致稳妥可补目录 fsync |
| B8 | `android:enableOnBackInvokedCallback="true"` 但未处理返回手势 | 若 Flet 未注册回调，返回手势可能出现"点了没反应"（Android 13+ 预测性返回） | **真机验证**：返回手势能否退出/关弹层；不行就把该属性设为 `false` |
| B9 | 未处理返回键关闭弹层 | 表单填一半按返回会直接退出应用，输入丢失 | 可接 `page.on_keyboard_event`，或后续用 `on_view_pop` |

#### 已验证是安全的（避免重复怀疑）

- **写入原子性**：`mkstemp` + `flush` + `fsync` + `os.replace`，失败清理临时文件 ✅
- **release 包不可调试**：合并清单里**没有** `android:debuggable` ✅
- **明文流量**：`targetSdk 34` 且未设 `usesCleartextTraffic` → 默认禁止 ✅
- **组件暴露面**：`MainActivity` 导出是启动器必需；`taskAffinity=""` 防任务劫持 ✅；
  两个 `FileProvider` 与 `SharePlusPendingIntent` 均 `exported=false` ✅
- **无外部存储、无网络请求、无动态代码加载** ✅
- **未使用 `eval`/`exec`/`pickle`/`subprocess`**，用户输入不进入任何命令或查询 ✅
- **构建排除**：`pyproject.toml` 的 `exclude` 含 `.flet`，开发数据不会被打进 APK ✅；
  `.gitignore` 也已忽略 `src/.flet/` ✅
- **正常数据往返完好**：课程 / 课程级备注 / 单节备注 / 颜色均无损 ✅
  （66 项自测 + 控件树校验全过）

#### 教训

- **"能解析"不等于"能用"**：本轮最严重的 A1/A2 都发生在 `json.loads` 成功**之后**。
  只保护解析步骤是错的安全边界；真正的边界应该是"装载数据这件事整体不许失败"。
- **兜底逻辑必须自己报错**：`load()` 选择重置数据是合理的（总比崩强），
  但**静默**重置只是把"崩溃"换成了"无声的数据丢失" —— 两者都不可接受。
  任何自动降级都必须让用户看见。
- **破坏性输入注入比通读代码有效得多**：A1 的 5 个触发点里，只有 1 个能靠读代码看出来，
  其余 4 个是跑一遍才暴露的。

#### 收尾：读日志 + 构建脚本 + 密钥泄露

**日志面（都是"无异常"的正面证据）**
- `flet run` 的 stdout/stderr：跑完全部交互（三个页面、翻周、滚动、开弹层、
  存备注、存设置）**零 traceback** —— 同时说明 `page.on_error` 兜底从未被触发
- 浏览器控制台：只有一条 `[log] Flutter app loaded`，
  **无 error / pageerror / requestfailed，也没有 Flutter 的
  "A RenderFlex overflowed" 溢出警告** → 课块行数预算与两列布局确实没有溢出
- 工程内没有任何 `.log` 文件，也没有 `.corrupt` 残留

**`tools/package_android.sh`（开发用，不进 APK，但有能力删掉整个工程）**
- 发现 footgun：同步分支里有 `rm -rf "$TARGET_DIR"`，而
  `TARGET_DIR="${BUILD_ROOT:-$HOME/build}/$(basename "$SOURCE_DIR")"`。
  只要 `BUILD_ROOT` 被指到工程上层（例如 `/mnt/d`），`TARGET_DIR` 就正好等于工程目录，
  这一步会把**整个工程删掉**。
- 已加三道护栏并逐项实测通过：
  ① `TARGET_DIR` 先归一化（`realpath -m`，防 `..` 或多写斜杠绕过判断）
  ② 与源目录相同 → 拒绝
  ③ 与源目录互相包含 → 拒绝。**两个方向的后果不同，必须分别拦**：
  构建目录在源目录内 → rsync 把工程拷进自己的子目录（自我递归）；
  源目录在构建目录内 → `rm -rf` 会连工程一起删掉。
  （第一版护栏把第 ③ 条写反了方向，是**跑测试才发现的** —— 没测就上线等于给虚假安全感）
- 顺带修正脚本头注释：它默认构建的是 **release** 包（只是用 debug 密钥签名），
  原文写成 "构建 debug APK" 会误导
- `.gitignore` 补上 `dist/`：脚本会把 APK 拷到那里，与 `build/` 一样不该进版本库

**密钥泄露面**
- 搜 `*.jks / *.keystore / *.p12 / *.pem / *.key` → **无**
- 全文搜 `password|secret|token|api_key|PRIVATE KEY` → 唯一命中是构建命令里
  Java 信任库的口令 `changeit`：它是 Java 出厂默认值，且该信任库只含公开 CA 证书、
  无任何私钥，因此**不是真正的凭据**
- ⚠️ 但要记住：将来配正式签名（B1）时，keystore 口令**绝不能**写进
  `PROGRESS.md`、脚本或命令历史，否则会随仓库一起泄露

### 第 17 轮 · 重新打包 APK（含备注功能 + 两列布局 + 第 16 轮全部修复）

- 触发：上次产物早于字号调整、翻页动画、备注功能与安全修复，需要重打
- 命令与 9.2 节完全一致（热缓存），耗时 **91 秒**（14:04:08 → 14:05:39，退出码 0）
- **新产物**：`build/apk/class_schedule.apk`
  - 52,451,152 字节（50.0 MB）/ 552 个条目
  - SHA1 `0bd2c0956dfed0194b8d8221c0f97f98f60158c1`
    （与构建自带的 `.apk.sha1` 逐字一致，两处独立来源互证）
- **核验结果（全部通过）**

  | 项 | 结果 |
  |---|---|
  | `assets/sitepackages.zip` | 4,903,664 B / 564 条目 / **282 个 flet 文件** ✅ |
  | `assets/app.zip` | 30 条目，含 `core/*.pyc`、`state.pyc`、**`ui/note_form`** ✅ |
  | 原生库架构 | 仅 `arm64-v8a`（与 `pyproject.toml` 一致）✅ |
  | 清单 `debuggable` | **未命中**（release 包不可调试）✅ |
  | 清单权限 | `INTERNET` + `ACCESS_NETWORK_STATE`（Flet 模板 / 插件带入，见第 16 轮 B2/B3） |

- **这次构建仍然传了 `--skip-site-packages`** —— 即"依赖哈希命中，复用上次装好的
  site-packages"。R27 的教训正是：这个复用一旦与实际状态不符，构建照样报成功、
  APK 里却没有 flet（装到手机上直接闪退）。**所以每次打包后都必须打开 APK 核验，
  不能只看 flet 输出的 "Successfully built"**。
- 为此新增一次性核验脚本 `build/verify_apk.py`（放在 `build/` 下，不进版本库）
- 脚本自身也踩了坑并已修正 —— **带假警报的核验工具比没有更糟**：
  - `--compile-packages` 让包内是 `.pyc`，按 `.py` 找会误报"缺关键文件"
  - APK 里的 `AndroidManifest.xml` 是**二进制 XML**，字符串池用 UTF-16LE 存储，
    拿 UTF-8 字节去搜必然落空 → 会把"有权限"误报成"没权限"，
    同时也就**查不出 `debuggable`**（等于安全检查形同虚设）
- 签名与 `versionCode` 均未变（仍是 debug 签名 / versionCode 1），
  因此**可以直接覆盖安装**旧版，手机上的课表数据会保留 ✅
- 待办：把新 APK + `.sha1` 重新上传为 Release 附件（旧附件对应旧 SHA1）

#### 补记：为什么又打了一次（build 2）

用户反馈"装上新 APK 后没有增加新功能"。排查分四部分：

**一、包本身没问题（有证据）**
- 打开 APK 核验：`assets/app.zip` 里确实有 `ui/note_form.pyc`，
  而且能从 `ui/settings_view.pyc` 里读出字符串常量 —— 说明打进包的是**新代码**
- 读插件源码 `serious_python_android/lib/serious_python_android.dart`：
  它用 `key = 'app:' + versionName+versionCode+lastUpdateTime` 决定是否重新解压，
  **`lastUpdateTime` 每次重装都变** → 重装必然重新解压。插件注释里还专门写了
  "只用 versionName+versionCode 会让调试流程一直跑旧代码"。
  → **排除"装了新包却跑旧代码"这个可能**

**二、真正的缺陷："装的哪个包"无法判断**
`versionCode` 始终是 1、界面又不显示版本号，导致"装上没有"既不能证实也不能证伪 ——
你我都只能猜。已修：
- `config.APP_VERSION` / `config.APP_BUILD`（注释里写明要和 `pyproject.toml` 同步）
- 设置页底部显示 `版本 0.1.0（build 2）`
- `pyproject.toml` 的 `build_number` 1 → 2

**三、功能"看不见"是设计使然（需在文档讲清，避免下次再误判）**
| 功能 | 为何装完看不出 |
|---|---|
| 备注 | 周视图刻意未改；单日视图只有课程**真有备注**时才多出 `本节 …` 一行 |
| 块内两列布局 | 仅当块宽 ≥ `_SPLIT_MIN_WIDTH`(380)。手机竖屏单日块约 302px，**不触发** |
| 翻页动画 | 需点「上一周/下一周」才可见 |
| 字号 +2 | 唯一无条件可见的变化，但幅度小，不做并排对比很难察觉 |

→ **验证新包最快的两个办法**：① 设置页看版本号；
② 单日里**单击课程块**，应弹「本节课备注」而不是「编辑课程」。

**四、重打包踩的坑：R23 复发（重要）**
改 `build_number` 让 flet 重新生成了 Flutter 工程，**把 `gradle-wrapper.properties`
的 `distributionUrl` 从腾讯镜像改回了 `services.gradle.org`**。
wrapper 按 URL 哈希找缓存 → 原站哈希目录里没有完整发行包 → 去下载 224 MB，
实测 **46 KB/s**（≈1.3 小时），**443 秒后构建失败**。

- 现象识别：栈里出现 `org.gradle.wrapper.Download.downloadInternal`；
  且 `.gradle-home/wrapper/dists/<版本>/` 下多出一个哈希目录，里面只有 `.part`
- **处置（比恢复镜像更稳）**：把已下好的完整发行包（zip + 解压目录 + `.zip.ok` 标记）
  **预置到原站 URL 对应的哈希目录**。这样无论 flet 之后把配置改成什么，
  wrapper 都能命中缓存，不再依赖镜像，**这个坑不会再复发**
- 处置后构建 **56 秒**完成（对比失败那次 443 秒）
- 教训：`pyproject.toml` 一改就可能触发工程重生成，从而重置工程内的构建配置。
  能放到 `GRADLE_USER_HOME` 或缓存侧的修正就不要留在工程文件里

#### 第 17 轮的最终产物（build 2）

| | |
|---|---|
| 路径 | `build/apk/class_schedule.apk` |
| 大小 | 52,451,464 字节（50.0 MB） |
| SHA1 | `b5956f157f6c9810327c3accf05f10797f6c18c5` |
| 条目数 | 552 |
| `sitepackages.zip` | 4,903,664 B / 564 条目 / 282 个 flet ✅ |
| `app.zip` | 30 条目，含 `ui/note_form.pyc`，且 `ui/settings_view.pyc` 内有「版本」常量 ✅ |
| 原生库 | 仅 arm64-v8a ✅ |
| 清单 `debuggable` | 未命中 ✅ |
| `versionCode` / `versionName` | 2 / 0.1.0 |

#### 补记二：构建的网络依赖已消除（build 3）

**问题**：打包时 6 个任务 `downloadDartBridge_<abi>` 全部失败：

```
HttpHostConnectException: Connect to https://github.com:443
[20.205.243.166] failed: Connection timed out
```

24 秒快速失败。而同一时刻 WSL 里 `curl https://github.com` 却是 HTTP 200、连接 0.7ms
—— 两边解析到同一个 IP，行为却相反。

**根因**：WSL 有 `http_proxy=http://127.0.0.1:7892`，**而 Windows 侧的 JVM 默认不走代理**。
0.7ms 的连接时间本身也说明 WSL 走的是本地代理，不是真实外网往返。

**处置（两处，都是消除依赖而不是绕过症状）**
1. `SERIOUS_PYTHON_DART_BRIDGE_DIST` → 指向本地已有的
   `.flet-cache/dart-bridge/v1.9.0`（内含三个 ABI 的 .so，命名符合插件要求）。
   插件源码 `serious_python_android/android/build.gradle.kts:396-417` 写得很清楚：
   `if (dartBridgeDist == null) dependsOn("downloadDartBridge_$abi")`
   —— **有本地目录就根本不注册下载任务**，这条路彻底不需要 github。
2. `JAVA_TOOL_OPTIONS` 追加 `-Dhttps.proxyHost=127.0.0.1 -Dhttps.proxyPort=7892`，
   让 Windows 侧 JVM 也走代理，避免其它环节（如 Android 运行时）再撞同一面墙。

**结果**：构建 **26 秒**完成，`downloadDartBridge_*` 零失败。

**这一轮的元教训：不要用 `| tail` 截断构建输出。**
前两次失败我只看到 "BUILD FAILED"，根因被 `tail` 丢掉了，等于白跑两次。
这与第 4 轮记的"判断进度看文件系统，不要看日志"是同一类错误的另一面 ——
**日志要完整留下，再看关键片段。**

#### build 3 产物

| | |
|---|---|
| 路径 | `build/apk/class_schedule.apk` |
| 大小 | 52,451,384 字节（50.0 MB） |
| SHA1 | `c4306eec34d63d4c68e984b1af1c56e02353ed98` |
| `versionCode` | 3 |
| 唯一命名副本 | `class_schedule-v0.1.0-build3-c4306eec.apk` |
| 核验 | `sitepackages.zip` 282 个 flet ✅；`app.zip` 含 `note_form`，且能从 `core/config.pyc` 读出 `0.1.0`、从 `ui/settings_view.pyc` 读出 `版本` ✅ |

- 版本号从页尾移到**设置页最顶部**（build 2 放在页尾，需要滚动才看得到 —— 实测因此被误判）
- ⚠️ **`flet build` 每次会清空 `build/apk/`**：手工放的唯一命名副本活不过下一次构建，
  必须在构建之后生成

#### ⚠️ 未解决：真机安装疑似无效

用户反馈：多次安装后手机仍跑最初版本，**卸载后重装也一样**。
全新安装不可能装出旧代码，因此怀疑传输环节留了同名旧副本，或从 Release 下载了旧附件。

- 我此前据"APK 内容正确 + 插件会重新解压"就断定"新代码已在手机上运行"，
  **这个结论是错的**。核验 APK 内容必要但不充分 —— 我从未验证过设备上装的是什么。
- 现在有了可判定的锚点：装后看「设置」页**顶部**有没有 `版本 0.1.0（build 3）`；
  或单日里单击课程块，应弹「本节课备注」而不是「编辑课程」。
