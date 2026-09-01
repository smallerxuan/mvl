/*
 * mvl_config.h —— MVL 库可配置参数（全部带默认值，可用 -D 编译宏覆盖）
 *
 * 覆盖方式（任选其一）：
 *   1. 编译命令行：  -DMVL_MSG_QUEUE_DEPTH=32
 *   2. 在包含 mvl 头文件之前由工程自行 #define
 */
#ifndef _MVL_CONFIG_H_
#define _MVL_CONFIG_H_

/* ---- mvl_msg：消息队列 ---- */

/* 消息队列深度（每条消息 = 函数指针 + 上下文指针） */
#ifndef MVL_MSG_QUEUE_DEPTH
#define MVL_MSG_QUEUE_DEPTH          16
#endif

/* 消息分发周期（lv_timer 触发间隔），最坏消费延迟 ≈ 一个周期。
 * 仅作为参考默认值提供给集成者创建分发定时器使用，库本体不依赖它。 */
#ifndef MVL_MSG_DISPATCH_PERIOD_MS
#define MVL_MSG_DISPATCH_PERIOD_MS   30
#endif

/* ---- mvl_evt：事件总线 ---- */

/* 事件 ID 空间大小（订阅表为 [MVL_EVT_MAX_ID][每事件订阅数] 的二维数组，
 * RAM 占用 ≈ MVL_EVT_MAX_ID * MVL_EVT_MAX_SUBS_PER_EVT * sizeof(sub_t)）。
 * 事件 ID 必须从 1 开始连续编号，且小于 MVL_EVT_MAX_ID。 */
#ifndef MVL_EVT_MAX_ID
#define MVL_EVT_MAX_ID               128
#endif

/* 每个事件的最大订阅者数 */
#ifndef MVL_EVT_MAX_SUBS_PER_EVT
#define MVL_EVT_MAX_SUBS_PER_EVT     4
#endif

/* LVGL 投递池深度（≈ 单个分发周期内可能积压的 LVGL 事件数上限）。
 * 池满时事件被丢弃并计入 mvl_evt_drop_count()。 */
#ifndef MVL_EVT_LVGL_JOB_POOL_SIZE
#define MVL_EVT_LVGL_JOB_POOL_SIZE   8
#endif

#endif /* _MVL_CONFIG_H_ */
