/*
 * demo_events.h —— 应用事件 ID 定义（MVL 库不内置任何产品事件）
 *
 * 约定：从 1 开始，按模块分段，小于 MVL_EVT_MAX_ID（默认 128）。
 */
#ifndef _DEMO_EVENTS_H_
#define _DEMO_EVENTS_H_

typedef enum {
    EVT_NONE = 0,

    /* 网络段 32~63（后台 → UI 的状态事件） */
    EVT_WIFI_SCAN_UPDATED = 32,   /* 扫描结果已更新（数据本体读 Model 快照） */
    EVT_WIFI_CONN_CHANGED,        /* 连接状态已变更（读 Model 快照） */

    /* 命令段 96~（UI → 后台的命令事件） */
    EVT_CMD_WIFI_SCAN = 96,       /* 触发扫描（net_manage 任务执行） */
    EVT_CMD_WIFI_CONNECT,         /* 连接，凭据读 Model 快照（net_manage 任务执行） */
} demo_evt_id_t;

#endif /* _DEMO_EVENTS_H_ */
