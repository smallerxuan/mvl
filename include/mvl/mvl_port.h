/*
 * mvl_port.h —— MVL 移植抽象层
 *
 * 库本体（mvl_msg / mvl_evt）只依赖本头文件声明的接口，不直接依赖任何
 * RTOS API。集成时须为工程链接恰好一个移植实现：
 *
 *   port/posix/     —— Linux/macOS 主机（pthread），用于 host 仿真与单元测试
 *   port/freertos/  —— vanilla FreeRTOS 参考移植（无参临界区形式）
 *   port/esp_idf/   —— ESP-IDF 参考移植（SMP 持锁临界区形式）
 *
 * 移植到其他 RTOS 时，照着 port/ 下任一参考实现补齐以下接口即可。
 */
#ifndef _MVL_PORT_H_
#define _MVL_PORT_H_

#ifdef __cplusplus
extern "C" {
#endif

#include <stddef.h>
#include <stdint.h>

/* 通用返回值约定 */
#define MVL_PORT_OK     0
#define MVL_PORT_FAIL   (-1)

/* mvl_port_queue_send/receive 的 timeout_ms 特殊值 */
#define MVL_PORT_WAIT_FOREVER   ((uint32_t)-1)

/* ---- 队列（句柄语义由移植层定义，库内一律以 void * 持有） ---- */

/** @brief 创建队列。len = 元素个数，item_size = 单元素字节数。失败返回 NULL */
void *mvl_port_queue_create(size_t len, size_t item_size);

/**
 * @brief 任务上下文发送（值拷贝）
 * @param timeout_ms 0 = 不等待（满即失败）；MVL_PORT_WAIT_FOREVER = 永久阻塞
 * @return MVL_PORT_OK / MVL_PORT_FAIL
 */
int   mvl_port_queue_send(void *q, const void *item, uint32_t timeout_ms);

/** @brief ISR 上下文发送（不允许阻塞，满即失败） */
int   mvl_port_queue_send_isr(void *q, const void *item);

/**
 * @brief 任务上下文接收（值拷贝）
 * @param timeout_ms 同 mvl_port_queue_send
 * @return MVL_PORT_OK 收到；MVL_PORT_FAIL 超时/空
 */
int   mvl_port_queue_receive(void *q, void *item, uint32_t timeout_ms);

/* ---- 临界区（保护投递池等小块共享状态，须支持嵌套之外的常规用法） ---- */

void  mvl_port_critical_enter(void);
void  mvl_port_critical_exit(void);
void  mvl_port_critical_enter_isr(void);
void  mvl_port_critical_exit_isr(void);

/* ---- 互斥锁（供 Model 等模式代码保护状态结构整体拷贝；库本体不依赖，
 *      但纳入移植层可让 examples/templates 与 mvl-gen 生成物保持平台无关） ---- */

/** @brief 创建互斥锁。失败返回 NULL */
void *mvl_port_mutex_create(void);
void  mvl_port_mutex_lock(void *m);
void  mvl_port_mutex_unlock(void *m);

/* ---- 断言（移植层可映射到 configASSERT / assert） ---- */
#ifndef mvl_port_assert
#include <assert.h>
#define mvl_port_assert(x)  assert(x)
#endif

#ifdef __cplusplus
}
#endif

#endif /* _MVL_PORT_H_ */
