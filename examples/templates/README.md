# MVL 骨架模板（examples/templates/）

MVL 库本体只提供机制层（`mvl_msg` + `mvl_evt`）；Model / ViewModel / View
是**模式代码**——状态结构天然与产品相关，无法做成通用库。本目录提供经过
真机验证的写法骨架，复制到工程后按 `<占位符>` 注释修改即可。

| 文件 | 对应层 | 要点 |
|---|---|---|
| `app_events.h` | 事件表 | 应用自定义事件 ID：从 1 开始、按模块分段、小于 `MVL_EVT_MAX_ID` |
| `mvl_model.h/.c` | Model | 状态中心：只能经 `set_xxx()` 写（写状态+发事件绑定），UI 侧只读快照 |
| `mvl_vm.h/.c` | ViewModel | 启动期一次性注册全部订阅；回调内读快照 → 调 View 接口 |
| `mvl_view_page.h/.c` | View | 每页一个文件，唯一允许认识 UI 控件（lv_* / GUI Guider）的手写层 |

配套集成步骤（main 侧）：

```c
/* 启动顺序不能乱（陷阱见 docs/user/pitfalls.md）： */
mvl_msg_init();      /* 1. 基础设施 */
mvl_evt_init();
mvl_model_init();

mvl_vm_init();       /* 2. 全部订阅注册（须在事件到达前完成） */

/* 3. 挂载消费点（二选一）：
   a) 自管 LVGL 主循环：循环内周期调用 mvl_msg_process();
   b) esp_lvgl_port 托管：LVGL 任务上下文创建 lv_timer 周期调用 */
lv_timer_create(dispatch_timer_cb, MVL_MSG_DISPATCH_PERIOD_MS, NULL);
```

互斥锁说明：模板中的状态锁使用移植层 `mvl_port_mutex_*`（见 mvl_port.h），
因此模板与 mvl-gen 生成物都是平台无关的，无需随平台改写。

也可以用 `tools/mvl-gen` 从 YAML 接线描述直接生成这些骨架（含设计时静态
检查），见 tools/README.md。
