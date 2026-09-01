#include "mvl/mvl_evt.h"
#include "mvl/mvl_msg.h"
#include "mvl/mvl_port.h"

#include <string.h>

typedef struct {
    bool          used;     /* 任务订阅的 cb 可为 NULL，需独立的占用标志 */
    mvl_evt_cb_t  cb;
    mvl_evt_ctx_t ctx;
    void         *queue;
} sub_t;

/* LVGL 投递作业：回调 + 事件值拷贝 */
typedef struct {
    mvl_evt_cb_t cb;
    mvl_evt_t    evt;
} lvgl_job_t;

static sub_t      s_subs[MVL_EVT_MAX_ID][MVL_EVT_MAX_SUBS_PER_EVT];
static lvgl_job_t s_pool[MVL_EVT_LVGL_JOB_POOL_SIZE];
static bool       s_pool_used[MVL_EVT_LVGL_JOB_POOL_SIZE];
static volatile uint32_t s_drop_cnt;    /* 丢事件计数，调试时观察 */

void mvl_evt_init(void)
{
    memset(s_subs, 0, sizeof(s_subs));
    memset(s_pool_used, 0, sizeof(s_pool_used));
    s_drop_cnt = 0;
}

bool mvl_evt_subscribe(mvl_evt_id_t id, mvl_evt_cb_t cb,
                       mvl_evt_ctx_t ctx, void *queue)
{
    if (id == 0 || id >= MVL_EVT_MAX_ID) return false;
    if (ctx == MVL_EVT_CTX_LVGL && cb == NULL)    return false;
    if (ctx == MVL_EVT_CTX_TASK  && queue == NULL) return false;

    for (int i = 0; i < MVL_EVT_MAX_SUBS_PER_EVT; i++) {
        if (!s_subs[id][i].used) {
            s_subs[id][i].used  = true;
            s_subs[id][i].cb    = cb;
            s_subs[id][i].ctx   = ctx;
            s_subs[id][i].queue = queue;
            return true;
        }
    }
    return false;   /* 订阅者超上限 */
}

/* ---- LVGL 投递池：临界区保护，任务 / ISR 通用 ---- */

static lvgl_job_t *job_alloc(bool from_isr)
{
    lvgl_job_t *job = NULL;

    if (from_isr) {
        mvl_port_critical_enter_isr();
        for (int i = 0; i < MVL_EVT_LVGL_JOB_POOL_SIZE; i++) {
            if (!s_pool_used[i]) { s_pool_used[i] = true; job = &s_pool[i]; break; }
        }
        mvl_port_critical_exit_isr();
    } else {
        mvl_port_critical_enter();
        for (int i = 0; i < MVL_EVT_LVGL_JOB_POOL_SIZE; i++) {
            if (!s_pool_used[i]) { s_pool_used[i] = true; job = &s_pool[i]; break; }
        }
        mvl_port_critical_exit();
    }
    return job;
}

static void job_free(lvgl_job_t *job)
{
    /* 仅在 LVGL 主任务调用；单个 bool 写与临界区内的扫描不会互相破坏 */
    s_pool_used[job - s_pool] = false;
}

/* 在 LVGL 主任务执行（由 mvl_msg 调度） */
static void dispatch_in_lvgl(void *ctx)
{
    lvgl_job_t *job = (lvgl_job_t *)ctx;

    if (job->cb) job->cb(&job->evt);
    job_free(job);
}

static bool do_publish(mvl_evt_id_t id, const mvl_evt_data_t *data, bool from_isr)
{
    if (id == 0 || id >= MVL_EVT_MAX_ID) return false;

    for (int i = 0; i < MVL_EVT_MAX_SUBS_PER_EVT; i++) {
        sub_t *s = &s_subs[id][i];
        if (!s->used) continue;

        if (s->ctx == MVL_EVT_CTX_TASK) {
            /* 事件值拷贝后直接投到订阅任务的队列，不阻塞发布者 */
            mvl_evt_t evt = { .id = id };
            if (data) evt.data = *data;

            int rc = from_isr ? mvl_port_queue_send_isr(s->queue, &evt)
                              : mvl_port_queue_send(s->queue, &evt, 0);
            if (rc != MVL_PORT_OK) s_drop_cnt++;
        } else {
            lvgl_job_t *job = job_alloc(from_isr);
            if (job == NULL) { s_drop_cnt++; continue; }    /* 池满丢弃 */

            job->cb      = s->cb;
            job->evt.id  = id;
            if (data) job->evt.data = *data;

            if (from_isr) mvl_msg_post_isr(dispatch_in_lvgl, job);
            else          mvl_msg_post(dispatch_in_lvgl, job);
        }
    }
    return true;
}

bool mvl_evt_publish(mvl_evt_id_t id, const mvl_evt_data_t *data)
{
    return do_publish(id, data, false);
}

bool mvl_evt_publish_isr(mvl_evt_id_t id, const mvl_evt_data_t *data)
{
    return do_publish(id, data, true);
}

uint32_t mvl_evt_drop_count(void)
{
    return s_drop_cnt;
}
