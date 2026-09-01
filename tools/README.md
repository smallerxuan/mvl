# mvl-gen —— MVL 接线设计代码生成工具

MVL（MVVM-Lite）的配套 CLI：以一份 YAML「接线设计」为唯一事实源，完成
设计时静态检查、C 骨架代码生成、mermaid 接线图导出。只设计"接线"，不设计
界面（UI 布局是 GUI Guider 的领域）。模式与规则依据见 ../docs/design/design.md
与 ../docs/user/pitfalls.md。

## 安装

```bash
cd tools
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"   # 去掉 .[dev] 则仅装运行依赖
```

## 用法

```bash
# 1. 静态检查（C1~C4 / C7 / C8；有错误时退出码为 1）
mvl-gen check examples/wifi_module.yaml

# 2. 生成代码到指定目录
mvl-gen generate examples/wifi_module.yaml -o path/to/main/ui/

# 3. 导出 mermaid 接线图
mvl-gen diagram examples/wifi_module.yaml -o docs/wiring.md
```

`generate` 产物：

| 文件 | 内容 |
|---|---|
| `mvl_events.h` | 事件 ID 枚举（分段注释 + EVT_APP_MAX 构造期校验），全量重生成 |
| `mvl_model.h/.c` | `mvl_state_t`、`mvl_model_init/snapshot`、`set_xxx` 自动绑定「互斥写 + 发布事件」 |
| `mvl_vm.h/.c` | ViewModel 订阅注册表 + LVGL 回调 stub（读快照 → 调 View 接口） |
| `mvl_view_<page>.h/.c` | View 接口声明 + 空实现骨架（唯一允许 include gui_guider.h 的文件） |
| `mvl_task_<task>.c` | 任务订阅者骨架：建队列、注册订阅、`switch(evt.id)` 分发循环 |
| `wiring_report.md` | 发布/订阅矩阵、Model 字段表、View 接口表、静态检查结论 |

## USER CODE 段（重新生成不丢手写代码）

生成文件内嵌 CubeMX 惯例的保留段：

```c
/* USER CODE BEGIN on_wifi_scan_updated */
... 手写业务逻辑，重新生成时原样保留 ...
/* USER CODE END on_wifi_scan_updated */
```

骨架（订阅表、函数签名、枚举）每次全量重生成；两段标记之间的内容不动。
因此：改接线关系 → 改 YAML → 重新生成；改业务逻辑 → 直接写 USER CODE 段。

## 静态检查规则（《方案》§5）

| # | 规则 | 级别 |
|---|---|---|
| C1 | 发布者 lvgl 且订阅者 lvgl → 自我死锁风险 | 错误 |
| C2 | 事件载荷 > 8 字节 | 错误 |
| C3 | ISR 发布的事件有 LVGL 订阅但未配置 `config.lvgl_job_pool` | 错误 |
| C4 | 事件无订阅者/无发布者、Model 字段疑似无人读写 | 警告 |
| C5 | set_xxx 写状态但未发布事件 | 生成器构造保证 |
| C6 | 基础设施 init 先于订阅注册 | 生成器构造保证 |
| C7 | 载荷含指针类型 | 错误 |
| C8 | 事件 ID 撞号/越段/越界、View 接口签名重复 | 错误 |

## YAML Schema

见 `examples/wifi_module.yaml`（WiFi 模块完整样例，生成结果骨架与
真机验证过的手写实现一致）。要点：

- `model`：`mvl_state_t` 字段表（`name` / `type` / `doc`）；
- `types`：可选，契约类型（typedef/enum/#define）的原始 C 片段，原样进入
  `mvl_model.h` 的 USER CODE 段；
- `setters`：Model 写接口表，`event` 绑定发布后自动完成「互斥写 + 发事件」，
  省略 `event` 则只写不发；
- `events`：`id` / `segment`（段基址，段内自动编号；可用 `value` 显式指定）
  / `payload`（`none` 或 ≤8 字节非指针 C 类型）/ `publishers` / `subscribers`；
- `view_interfaces`：各页面 View 接口签名（仅声明，不含实现）；
- `config.lvgl_job_pool`：LVGL 投递池深度，C3 检查依据。

执行上下文词表：发布者 `lvgl / task / sys_evt / isr`；
订阅者 `lvgl`（ViewModel 回调）/ `task_queue`（任务队列）。

## mvl-studio：图形化编辑器（可选）

不方便手写 YAML 时，用 mvl-studio「勾勾选选、填填表格」完成接线配置。
GUI 只是 YAML 的薄编辑器——唯一事实源仍是 `mvl_project.yaml` 文件本身。

概念速览（编辑器左侧树的每个节点对应一行；选中节点时右侧说明框有详解）：

| 概念 | 一句话 | 详见 docs/design/design.md |
|---|---|---|
| 契约类型 types | 三方共享的 C 类型，原样进 mvl_model.h | §5.7 共享契约 |
| Model 字段 | mvl_state_t 字段表，唯一权威数据源 | §5.2 Model 状态中心 |
| 写接口 setters | 改 Model 的唯一入口，自动「写状态 + 发事件」 | §5.2 |
| 事件 events | 模块间解耦的通道，谁发谁收在此接线 | §4 事件总线 |
| 发布者 / 订阅者 | 事件的产生方（任务/ISR）与消费方（LVGL 回调/任务队列） | §4.5 两种订阅上下文 |
| View 接口 | 页面函数签名，只生成声明，实现手写 | §5.3 ViewModel / View |
| 载荷 / 快照 | 8 字节值拷贝；大数据走「事件 + Model 快照」 | §4.4 / §5.4 |
| lvgl_job_pool | LVGL 投递池深度（C3 检查依据） | §4.6 LVGL 投递池 |

```bash
pip install -e ".[gui]"   # 或 .[dev]（已含 PySide6）
mvl-studio                          # 从模板新建
mvl-studio path/to/mvl_project.yaml # 直接打开已有文件
```

工作流：

1. **新建**（复制 `examples/mvl_project.template.yaml` 的示例占位）或**打开**已有 YAML；
2. 左侧树选中节点（project / config / types / model / setters / events
   （含发布者、订阅者）/ view_interfaces（含函数）），右侧用表单或表格编辑，
   context 等枚举字段为下拉框；
3. 底部检查面板实时（防抖 400ms）全量跑 C1~C4/C7/C8，双击检查行定位到树节点；
   有错误时保存仍允许（给出提示）；
4. 右侧「架构示意图」标签页按 MVVM 五层泳道实时绘制当前接线（后台任务 /
   Model / 事件总线 / ViewModel / View），数据来自编辑中的文档，随修改重绘；
5. **保存**得到合法 YAML（写出的文件保证能被 mvl-gen 加载；注释不保留）；
6. **生成代码**按钮选输出目录，等价于 `mvl-gen generate`，
   也可在 CI 里对该 YAML 直接跑 mvl-gen。

无显示器环境跑测试用 `QT_QPA_PLATFORM=offscreen`（见 tests/test_studio.py）。

**Linux 启动报错 `xcb-cursor0 or libxcb-cursor0 is needed`**：PySide6 ≥ 6.5
的 xcb 平台插件运行时依赖系统库 `libxcb-cursor0`（非 Python 包，pip 装不了）。
两种解决：

```bash
# 方案一（推荐）：系统包安装，一劳永逸
sudo apt install libxcb-cursor0

# 方案二（无 sudo）：解包 .deb 到项目内，用 LD_LIBRARY_PATH 指过去
cd tools && mkdir -p .qtlibs && cd .qtlibs
apt download libxcb-cursor0 && dpkg -x libxcb-cursor0_*.deb . && cd ..
LD_LIBRARY_PATH="$(echo "$PWD"/.qtlibs/usr/lib/*/)" mvl-studio
```

方案二只对当前机器该路径有效，且 `.qtlibs/` 已被 .gitignore 排除，不会进版本库。

## 测试

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/ -q
```

覆盖：mvl-gen 验收（WiFi 样例生成 + 骨架断言）、全部错误 YAML 构造
（LVGL→LVGL、载荷超 8 字节、载荷含指针、ID 撞号/越段、ISR 未配池、
签名重复）、USER CODE 段保留、mermaid 导出、CLI 退出码；
mvl-studio 数据层 round-trip（新建→改字段→保存→重载一致）、
检查面板错误展示与节点定位、GUI offscreen 冒烟。
