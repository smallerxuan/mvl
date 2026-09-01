/*
 * port/esp_idf —— ESP-IDF 参考移植
 *
 * 与 vanilla FreeRTOS 移植的差异（ESP-IDF SMP 适配）：
 * - 临界区必须持自旋锁：taskENTER_CRITICAL(&mux) / taskEXIT_CRITICAL(&mux)，
 *   双核间仅靠调度锁无法互斥；
 * - ISR 变体同理（taskENTER_CRITICAL_ISR / taskEXIT_CRITICAL_ISR）。
 *
 * 消费点适配提示：若 LVGL 主循环由 esp_lvgl_port 托管（lvgl_port_task），
 * 无法在其循环内插入 mvl_msg_process()，可改为在 LVGL 任务上下文创建
 * lv_timer 周期调用 mvl_msg_process()，语义等价（见 docs/design/design.md）。
 */
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"

/* 断言映射到 configASSERT（须在包含 mvl_port.h 之前定义，其 #ifndef 才生效） */
#define mvl_port_assert(x)  configASSERT(x)

#include "mvl/mvl_port.h"

void *mvl_port_queue_create(size_t len, size_t item_size)
{
    return (void *)xQueueCreate((UBaseType_t)len, (UBaseType_t)item_size);
}

int mvl_port_queue_send(void *q, const void *item, uint32_t timeout_ms)
{
    TickType_t ticks = (timeout_ms == MVL_PORT_WAIT_FOREVER)
                       ? portMAX_DELAY
                       : pdMS_TO_TICKS(timeout_ms);
    return xQueueSend((QueueHandle_t)q, item, ticks) == pdTRUE
           ? MVL_PORT_OK : MVL_PORT_FAIL;
}

int mvl_port_queue_send_isr(void *q, const void *item)
{
    BaseType_t woken = pdFALSE;
    BaseType_t rc = xQueueSendFromISR((QueueHandle_t)q, item, &woken);
    portYIELD_FROM_ISR(woken);
    return rc == pdTRUE ? MVL_PORT_OK : MVL_PORT_FAIL;
}

int mvl_port_queue_receive(void *q, void *item, uint32_t timeout_ms)
{
    TickType_t ticks = (timeout_ms == MVL_PORT_WAIT_FOREVER)
                       ? portMAX_DELAY
                       : pdMS_TO_TICKS(timeout_ms);
    return xQueueReceive((QueueHandle_t)q, item, ticks) == pdTRUE
           ? MVL_PORT_OK : MVL_PORT_FAIL;
}

/* SMP 下临界区必须持自旋锁，双核互斥才成立 */
static portMUX_TYPE s_crit_mux = portMUX_INITIALIZER_UNLOCKED;

void mvl_port_critical_enter(void)
{
    taskENTER_CRITICAL(&s_crit_mux);
}

void mvl_port_critical_exit(void)
{
    taskEXIT_CRITICAL(&s_crit_mux);
}

void mvl_port_critical_enter_isr(void)
{
    taskENTER_CRITICAL_ISR(&s_crit_mux);
}

void mvl_port_critical_exit_isr(void)
{
    taskEXIT_CRITICAL_ISR(&s_crit_mux);
}

/* ---- 互斥锁（供 Model 等模式代码使用；FreeRTOS 以 mutex 信号量实现） ---- */

void *mvl_port_mutex_create(void)
{
    return (void *)xSemaphoreCreateMutex();
}

void mvl_port_mutex_lock(void *m)
{
    xSemaphoreTake((SemaphoreHandle_t)m, portMAX_DELAY);
}

void mvl_port_mutex_unlock(void *m)
{
    xSemaphoreGive((SemaphoreHandle_t)m);
}
