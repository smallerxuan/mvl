/*
 * port/freertos —— vanilla FreeRTOS 参考移植
 *
 * 适用：直接使用 FreeRTOS 内核（非 ESP-IDF）的工程。
 * 说明：无参临界区形式（taskENTER_CRITICAL() 不带 mux 参数），
 *       对应单核 FreeRTOS 或 SMP 之前的经典 API；
 *       ESP-IDF（SMP）用户请改用 port/esp_idf（临界区必须持自旋锁）。
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

void mvl_port_critical_enter(void)
{
    taskENTER_CRITICAL();
}

void mvl_port_critical_exit(void)
{
    taskEXIT_CRITICAL();
}

/* FROM_ISR 的进出须配对传递中断状态保存值（经典 FreeRTOS 约定） */
static UBaseType_t s_isr_saved;

void mvl_port_critical_enter_isr(void)
{
    s_isr_saved = taskENTER_CRITICAL_FROM_ISR();
}

void mvl_port_critical_exit_isr(void)
{
    taskEXIT_CRITICAL_FROM_ISR(s_isr_saved);
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
