/*
 * mvl_evt —— 事件总线
 *
 * 设计要点：
 * - 订阅回调永远在订阅者自己的上下文执行：LVGL 订阅者经 mvl_msg 投递到
 *   LVGL 主任务，任务订阅者投递到它自己的队列；绝不在发布者线程里直接执行回调；
 * - 事件负载固定 8 字节值拷贝，绕开指针生命周期问题；
 * - 订阅表启动期静态注册、运行期不增删，全程免锁。
 *
 * 事件 ID 由应用自行定义（库不内置任何产品事件）：从 1 开始连续编号，
 * 按模块分段，且小于 MVL_EVT_MAX_ID（见 mvl_config.h）。示例：
 *
 *   typedef enum {
 *       EVT_NONE = 0,
 *       EVT_WIFI_SCAN_UPDATED = 32,   // 网络段 32~63
 *       EVT_CMD_WIFI_CONNECT  = 96,   // 命令段 96~
 *   } app_evt_id_t;
 */
#ifndef _MVL_EVT_H_
#define _MVL_EVT_H_

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include <stdbool.h>

#include "mvl_config.h"

/**
 * @brief 事件 ID：全系统唯一，由应用按模块分段定义（0 保留）
 */
typedef uint16_t mvl_evt_id_t;

/**
 * @brief 事件负载：固定 8 字节，发布时值拷贝
 * @note 禁止存放指向易失内存的指针；大数据用「就绪事件 + Model 快照」模式
 */
typedef union {
    int32_t  i32;
    uint32_t u32;
    float    f32;
    bool     b;
    uint8_t  raw[8];
} mvl_evt_data_t;

typedef struct {
    mvl_evt_id_t   id;
    mvl_evt_data_t data;
} mvl_evt_t;

typedef void (*mvl_evt_cb_t)(const mvl_evt_t *evt);

/**
 * @brief 订阅者执行上下文
 */
typedef enum {
    MVL_EVT_CTX_LVGL = 0,  /* 回调在 LVGL 主任务执行，可安全调 lv_*() */
    MVL_EVT_CTX_TASK       /* 回调在订阅任务上下文执行，queue 为其接收队列 */
} mvl_evt_ctx_t;

void mvl_evt_init(void);

/**
 * @brief 订阅事件
 * @param cb     ctx = MVL_EVT_CTX_LVGL 时的回调（在 LVGL 主任务执行）；
 *               ctx = MVL_EVT_CTX_TASK 时传 NULL，任务自行从 queue 取事件
 * @param queue  ctx = MVL_EVT_CTX_TASK 时传入订阅者自己的队列句柄
 *               （void *，元素类型须为 mvl_evt_t，由 mvl_port_queue_create 创建）；
 *               ctx = MVL_EVT_CTX_LVGL 时传 NULL
 * @note 在系统启动期一次性注册完毕，运行期不增删
 */
bool mvl_evt_subscribe(mvl_evt_id_t id, mvl_evt_cb_t cb,
                       mvl_evt_ctx_t ctx, void *queue);

/** @brief 发布事件（任务上下文）。data 会被值拷贝，发布后可立即复用 / 释放 */
bool mvl_evt_publish(mvl_evt_id_t id, const mvl_evt_data_t *data);

/** @brief 发布事件（ISR 上下文）。订阅者越多耗时越长，ISR 内慎用 */
bool mvl_evt_publish_isr(mvl_evt_id_t id, const mvl_evt_data_t *data);

/**
 * @brief 累计丢事件计数（LVGL 投递池满 / 任务订阅队列满时递增）
 * @note 调试观测用；正常系统应恒为 0
 */
uint32_t mvl_evt_drop_count(void);

#ifdef __cplusplus
}
#endif

#endif /* _MVL_EVT_H_ */
