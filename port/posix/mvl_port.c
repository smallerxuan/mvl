/*
 * port/posix —— MVL 主机（Linux/macOS）参考移植
 *
 * 用途：host 仿真示例与单元测试；让 MVL 总线逻辑无需硬件即可运行、进 CI。
 * 实现：队列 = 互斥锁 + 条件变量 + 环形缓冲；临界区 = 全局互斥锁。
 * 说明：主机没有真正的 ISR，_isr 变体退化为对应的任务态非阻塞版本。
 */
#include "mvl/mvl_port.h"

#include <pthread.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <errno.h>

typedef struct {
    pthread_mutex_t mu;
    pthread_cond_t  not_empty;
    pthread_cond_t  not_full;
    uint8_t        *buf;
    size_t          item_size;
    size_t          len;
    size_t          head;
    size_t          count;
} pqueue_t;

static void ms_to_timespec(uint32_t ms, struct timespec *ts)
{
    clock_gettime(CLOCK_REALTIME, ts);
    ts->tv_sec  += ms / 1000;
    ts->tv_nsec += (long)(ms % 1000) * 1000000L;
    if (ts->tv_nsec >= 1000000000L) {
        ts->tv_sec  += 1;
        ts->tv_nsec -= 1000000000L;
    }
}

void *mvl_port_queue_create(size_t len, size_t item_size)
{
    pqueue_t *q = calloc(1, sizeof(pqueue_t));
    if (q == NULL) return NULL;

    q->buf = malloc(len * item_size);
    if (q->buf == NULL) { free(q); return NULL; }

    pthread_mutex_init(&q->mu, NULL);
    pthread_cond_init(&q->not_empty, NULL);
    pthread_cond_init(&q->not_full, NULL);
    q->item_size = item_size;
    q->len       = len;
    q->head      = 0;
    q->count     = 0;
    return q;
}

/* 返回 MVL_PORT_OK / MVL_PORT_FAIL；调用前须已持有 q->mu */
static int queue_push_locked(pqueue_t *q, const void *item, uint32_t timeout_ms)
{
    if (timeout_ms == 0) {
        if (q->count == q->len) return MVL_PORT_FAIL;
    } else if (timeout_ms == MVL_PORT_WAIT_FOREVER) {
        while (q->count == q->len)
            pthread_cond_wait(&q->not_full, &q->mu);
    } else {
        struct timespec ts;
        ms_to_timespec(timeout_ms, &ts);
        while (q->count == q->len) {
            if (pthread_cond_timedwait(&q->not_full, &q->mu, &ts) == ETIMEDOUT)
                return MVL_PORT_FAIL;
        }
    }

    size_t tail = (q->head + q->count) % q->len;
    memcpy(q->buf + tail * q->item_size, item, q->item_size);
    q->count++;
    pthread_cond_signal(&q->not_empty);
    return MVL_PORT_OK;
}

static int queue_pop_locked(pqueue_t *q, void *item, uint32_t timeout_ms)
{
    if (timeout_ms == 0) {
        if (q->count == 0) return MVL_PORT_FAIL;
    } else if (timeout_ms == MVL_PORT_WAIT_FOREVER) {
        while (q->count == 0)
            pthread_cond_wait(&q->not_empty, &q->mu);
    } else {
        struct timespec ts;
        ms_to_timespec(timeout_ms, &ts);
        while (q->count == 0) {
            if (pthread_cond_timedwait(&q->not_empty, &q->mu, &ts) == ETIMEDOUT)
                return MVL_PORT_FAIL;
        }
    }

    memcpy(item, q->buf + q->head * q->item_size, q->item_size);
    q->head = (q->head + 1) % q->len;
    q->count--;
    pthread_cond_signal(&q->not_full);
    return MVL_PORT_OK;
}

int mvl_port_queue_send(void *q, const void *item, uint32_t timeout_ms)
{
    pqueue_t *pq = (pqueue_t *)q;
    int rc;

    pthread_mutex_lock(&pq->mu);
    rc = queue_push_locked(pq, item, timeout_ms);
    pthread_mutex_unlock(&pq->mu);
    return rc;
}

int mvl_port_queue_send_isr(void *q, const void *item)
{
    /* 主机无真实 ISR：退化为非阻塞发送 */
    return mvl_port_queue_send(q, item, 0);
}

int mvl_port_queue_receive(void *q, void *item, uint32_t timeout_ms)
{
    pqueue_t *pq = (pqueue_t *)q;
    int rc;

    pthread_mutex_lock(&pq->mu);
    rc = queue_pop_locked(pq, item, timeout_ms);
    pthread_mutex_unlock(&pq->mu);
    return rc;
}

/* ---- 临界区：全局互斥锁（主机无真实 ISR，_isr 变体相同） ---- */

static pthread_mutex_t s_crit = PTHREAD_MUTEX_INITIALIZER;

void mvl_port_critical_enter(void)      { pthread_mutex_lock(&s_crit); }
void mvl_port_critical_exit(void)       { pthread_mutex_unlock(&s_crit); }
void mvl_port_critical_enter_isr(void)  { pthread_mutex_lock(&s_crit); }
void mvl_port_critical_exit_isr(void)   { pthread_mutex_unlock(&s_crit); }

/* ---- 互斥锁（供 Model 等模式代码使用） ---- */

void *mvl_port_mutex_create(void)
{
    pthread_mutex_t *m = malloc(sizeof(pthread_mutex_t));
    if (m == NULL) return NULL;
    pthread_mutex_init(m, NULL);
    return m;
}

void mvl_port_mutex_lock(void *m)   { pthread_mutex_lock((pthread_mutex_t *)m); }
void mvl_port_mutex_unlock(void *m) { pthread_mutex_unlock((pthread_mutex_t *)m); }
