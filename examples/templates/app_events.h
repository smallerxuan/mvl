/*
 * app_events.h —— 应用事件 ID 表（模板）
 *
 * MVL 库不内置任何事件；事件 ID 由应用在此统一定义：
 * - 从 1 开始（0 保留），按模块分段，便于不同模块并行演进不撞号；
 * - 必须小于 MVL_EVT_MAX_ID（默认 128，见 mvl_config.h）；
 * - 每个事件注明：方向（后台→UI 状态 / UI→后台 命令）、载荷、数据本体在哪。
 */
#ifndef _APP_EVENTS_H_
#define _APP_EVENTS_H_

typedef enum {
    EVT_NONE = 0,

    /* <模块A> 段 32~63（后台 → UI 状态事件） */
    /* EVT_<模块A>_<状态>_UPDATED = 32,   数据本体读 Model 快照 <字段名> */

    /* <模块B> 段 64~95 */

    /* 命令段 96~（UI → 后台命令事件） */
    /* EVT_CMD_<动作> = 96,               参数经 Model <字段名> 传递，由 <任务名> 消费 */

    EVT_APP_MAX
} app_evt_id_t;

#endif /* _APP_EVENTS_H_ */
