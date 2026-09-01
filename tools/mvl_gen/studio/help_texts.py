"""studio/help_texts.py —— mvl-studio 的全部说明文案（集中存放，便于改文案/i18n）。

NODE_HELP：每类树节点一段说明，讲三件事——这是什么 / 这里填什么 / 生成后变成什么。
  kind 与 main_window._node_kind 的返回值一一对应：
  project / config / types / model / setters / events /
  publishers / subscribers / view_interfaces / functions
TOOLTIPS：树节点悬浮提示（各段说明的首句，单独维护以保持一句话长度）。
WELCOME：新建项目/首次启动时的「五步上手」。
"""

# {kind: (标题, 正文 HTML)}——正文支持换行富文本
NODE_HELP = {
    "project": (
        "项目",
        "<b>这是什么</b>：工程标识，一份 YAML = 一个项目的全部接线设计。<br/>"
        "<b>这里填什么</b>：项目名（进生成文件头注释与接线报告标题）、MVL 库版本号。<br/>"
        "<b>生成后变成什么</b>：不直接生成代码，是整份 mvl_project.yaml 的名片。<br/>"
        "<i>五步上手：① 填契约类型 → ② 定 Model 状态字段 → ③ 写接口绑定事件 → "
        "④ 事件接线（谁发谁收）→ ⑤ 声明 View 接口 → 生成代码。</i>",
    ),
    "config": (
        "全局配置",
        "<b>这是什么</b>：与 mvl_config.h 对应的全局参数。<br/>"
        "<b>这里填什么</b>：lvgl_job_pool = LVGL 投递池深度，即一个分发周期内最多积压的 "
        "LVGL 事件数（对应 MVL_EVT_LVGL_JOB_POOL_SIZE）。有 ISR 发布的事件且订阅者在 "
        "LVGL 上下文时必填（检查规则 C3）。<br/>"
        "<b>生成后变成什么</b>：作为静态检查依据；请在工程里用 -D 或宏定义保持同值。",
    ),
    "types": (
        "契约类型 types",
        "<b>这是什么</b>：Model / View / 后台三方共享的 C 类型（struct / enum / #define）。<br/>"
        "<b>这里填什么</b>：原始 C 片段。事件载荷（固定 8 字节）放不下的数据"
        "（如扫描结果数组）通过这些类型经「Model 快照」传递。<br/>"
        "<b>生成后变成什么</b>：内容原样进入生成的 mvl_model.h 的 USER CODE 段。",
    ),
    "model": (
        "Model 状态字段",
        "<b>这是什么</b>：系统状态结构 mvl_state_t 的字段表。Model 是全系统唯一权威数据源"
        "——UI 只许读快照，后台只许经「写接口」修改。<br/>"
        "<b>这里填什么</b>：字段名 / C 类型（数组写作 类型[N]，如 char[33]）/ 说明。<br/>"
        "<b>生成后变成什么</b>：mvl_model.h 里的 mvl_state_t 成员。",
    ),
    "setters": (
        "写接口 setters",
        "<b>这是什么</b>：修改 Model 的唯一入口 mvl_model_set_xxx()。<br/>"
        "<b>这里填什么</b>：接口名后缀、C 形参列表、绑定事件（可空）。绑定事件后生成代码"
        "自动完成「互斥写状态 + 发布事件」，UI 永不漏刷新；不绑事件 = 只写不发"
        "（适合命令参数，如待连接凭据）。<br/>"
        "<b>生成后变成什么</b>：mvl_model.c 里的 set_xxx 骨架，写字段的具体逻辑写在 "
        "USER CODE 段。",
    ),
    "events": (
        "事件 events",
        "<b>这是什么</b>：模块间解耦的通道。谁发布（哪个任务/ISR）→ 谁订阅"
        "（LVGL 回调或任务队列），在此接线。<br/>"
        "<b>这里填什么</b>：事件 ID（全系统唯一）、段基址（同段自动编号）、载荷"
        "（none 或 ≤8 字节、不含指针的 C 类型；大数据走「事件 + Model 快照」模式）。"
        "每行的发布者/订阅者在子节点里填。<br/>"
        "<b>生成后变成什么</b>：mvl_events.h 的枚举值，以及 mvl_vm.c / mvl_task_*.c 的"
        "订阅注册骨架。",
    ),
    "publishers": (
        "发布者 publishers",
        "<b>这是什么</b>：哪个模块在什么执行上下文产生该事件。<br/>"
        "<b>这里填什么</b>：模块名 + 上下文下拉（task / sys_evt / lvgl / isr）。"
        "ISR 发布者受 C3 规则约束（有 LVGL 订阅时必须在 config 里配 lvgl_job_pool）；"
        "lvgl 发布 + lvgl 订阅是错误组合（C1 自我死锁）。<br/>"
        "<b>生成后变成什么</b>：写接口或任务代码里的 mvl_evt_publish 调用点"
        "（接线报告中留档）。",
    ),
    "subscribers": (
        "订阅者 subscribers",
        "<b>这是什么</b>：事件送到哪。<br/>"
        "<b>这里填什么</b>：二选一——handler（ViewModel 回调名，在 LVGL 主任务执行，"
        "可安全操作 UI）或 task（目标任务名，事件进它的队列）；配上下文下拉"
        "（lvgl / task_queue）。<br/>"
        "<b>生成后变成什么</b>：handler → mvl_vm.c 的回调 stub + 订阅注册；"
        "task → mvl_task_&lt;任务名&gt;.c 的队列消费骨架。",
    ),
    "view_interfaces": (
        "View 接口",
        "<b>这是什么</b>：页面的显示 / 输入采集函数签名，ViewModel 与 View 之间的契约。<br/>"
        "<b>这里填什么</b>：页面名列表；每个页面的函数签名在子节点里填。<br/>"
        "<b>生成后变成什么</b>：mvl_view_&lt;page&gt;.h/.c——只生成声明和空骨架，"
        "函数体在 USER CODE 段手写，那是唯一允许碰 lv_* 控件的地方。",
    ),
    "functions": (
        "View 接口函数",
        "<b>这是什么</b>：当前页面的函数签名表。<br/>"
        "<b>这里填什么</b>：函数名 / C 形参 / 返回类型（缺省 void）/ 说明。"
        "函数名会自动加 mvl_view_&lt;page&gt;_ 前缀。<br/>"
        "<b>生成后变成什么</b>：mvl_view_&lt;page&gt;.h 的声明 + .c 的空实现骨架。",
    ),
}

# 树节点悬浮提示（一句话）
TOOLTIPS = {
    "project": "工程标识：一份 YAML = 一个项目的全部接线设计",
    "config": "全局参数（lvgl_job_pool = LVGL 投递池深度）",
    "types": "Model / View / 后台三方共享的 C 类型，原样进 mvl_model.h",
    "model": "mvl_state_t 字段表——全系统唯一权威数据源",
    "setters": "修改 Model 的唯一入口，绑定事件后自动「写状态 + 发事件」",
    "events": "模块间解耦的通道：谁发布 → 谁订阅，在此接线",
    "publishers": "哪个模块在什么上下文产生该事件（ISR 受 C3 约束）",
    "subscribers": "事件送到哪：LVGL 回调或任务队列，二选一",
    "view_interfaces": "页面的显示 / 输入采集函数签名（只生成声明）",
    "functions": "当前页面的函数签名表",
}

WELCOME = (
    "<b>欢迎使用 mvl-studio</b>——MVL 接线设计编辑器。五步上手：<br/>"
    "① <b>契约类型</b>：定义三方共享的 C 类型（struct/enum/#define）<br/>"
    "② <b>Model 字段</b>：列出系统状态结构 mvl_state_t 的字段<br/>"
    "③ <b>写接口</b>：定义 set_xxx() 并绑定要发布的事件<br/>"
    "④ <b>事件</b>：接线——谁发布（任务/ISR）、谁订阅（LVGL 回调/任务队列）<br/>"
    "⑤ <b>View 接口</b>：声明各页面的显示/采集函数签名<br/>"
    "然后点工具栏「生成代码」。左侧选中任意节点，这里会显示对应说明；"
    "底部检查面板实时提示错误/警告，双击可定位。<br/>"
    "点上方「架构示意图」标签可查看当前接线的 MVVM 分层图。"
)
