/*
 * mvl_msg —— LVGL 8.x 线程安全消息队列（机制层）
 *
 * 核心约定（单写者原则）：
 * - 所有 UI 操作打包成「函数指针 + 上下文指针」消息，任何任务/ISR 均可投递；
 * - 消息只由 LVGL 主任务消费执行，回调内可安全调用任何 lv_* API；
 * - 消费点由集成者选择，二选一（详见 docs/design/design.md）：
 *     a) 自管 LVGL 主循环：在循环内周期调用 mvl_msg_process()；
 *     b) esp_lvgl_port 等托管组件：在 LVGL 任务上下文创建 lv_timer 周期调用，
 *        语义等价（参考 examples/）。
 */
#ifndef _MVL_MSG_H_
#define _MVL_MSG_H_

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include <stdbool.h>

#include "mvl_config.h"

/**
 * @brief LVGL 安全任务回调原型
 * @param ctx 用户上下文指针
 *
 * 该函数将在 LVGL 主任务中执行，可安全调用任何 lv_* API
 */
typedef void (*mvl_action_t)(void *ctx);

/**
 * @brief 初始化消息队列（须在任何 post 之前调用一次）
 */
void mvl_msg_init(void);

/**
 * @brief 向 LVGL 主任务投递任务（线程安全）
 * @param action 回调函数指针，不能为 NULL
 * @param ctx    传递给回调的上下文指针，可为 NULL
 *               （ctx 指向内存的生命周期须覆盖到回调执行完毕）
 *
 * 可在任意任务中调用。队列满时永久阻塞直到投递成功（关键事件不丢）。
 * 禁止在 LVGL 主任务（含回调）中调用本函数，否则可能自我死锁。
 */
void mvl_msg_post(mvl_action_t action, void *ctx);

/**
 * @brief 尝试投递任务（非阻塞，线程安全）
 * @return true 投递成功；false 队列已满，消息被丢弃
 * @note 适合高频可丢弃场景（如状态刷新）；关键事件请用阻塞版
 */
bool mvl_msg_try_post(mvl_action_t action, void *ctx);

/**
 * @brief 向 LVGL 主任务投递任务（ISR 安全）。队列满时消息将被丢弃。
 */
void mvl_msg_post_isr(mvl_action_t action, void *ctx);

/**
 * @brief 处理消息队列（仅在 LVGL 主任务中调用）
 *
 * 非阻塞地消费并执行当前队列中的所有消息。
 */
void mvl_msg_process(void);

#ifdef __cplusplus
}
#endif

#endif /* _MVL_MSG_H_ */
