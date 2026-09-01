/*
 * MVL host 单元测试（POSIX 移植层，无外部测试框架依赖）
 *
 * 覆盖：总线订阅路由（LVGL / 任务两种上下文）、投递池管理与丢包计数、
 *       载荷值拷贝语义、参数校验、消息队列基本行为。
 *
 * 编译配置（见 CMakeLists.txt）：
 *   MVL_MSG_QUEUE_DEPTH=4, MVL_EVT_MAX_ID=64,
 *   MVL_EVT_MAX_SUBS_PER_EVT=2, MVL_EVT_LVGL_JOB_POOL_SIZE=2
 */
#include "mvl/mvl_msg.h"
#include "mvl/mvl_evt.h"
#include "mvl/mvl_port.h"

#include <stdio.h>
#include <string.h>
#include <pthread.h>
#include <unistd.h>

static int s_checks = 0;
static int s_fails  = 0;

#define CHECK(cond) do {                                    \
    s_checks++;                                             \
    if (!(cond)) {                                          \
        s_fails++;                                          \
        printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); \
    }                                                       \
} while (0)

/* 测试用事件 ID（应用侧自定义，库不内置） */
#define EVT_A   1
#define EVT_B   2
#define EVT_C   3

/* ---------------------------------------------------------------- mvl_msg */

static int s_msg_ran[8];
static int s_msg_n;

static void msg_action(void *ctx)
{
    s_msg_ran[s_msg_n++] = (int)(intptr_t)ctx;
}

static void test_msg_basic(void)
{
    mvl_msg_init();

    mvl_msg_post(msg_action, (void *)(intptr_t)1);
    mvl_msg_post(msg_action, (void *)(intptr_t)2);
    CHECK(s_msg_n == 0);                 /* 未消费前不应执行 */

    mvl_msg_process();                   /* 模拟 LVGL 主任务消费 */
    CHECK(s_msg_n == 2);
    CHECK(s_msg_ran[0] == 1);            /* FIFO 顺序 */
    CHECK(s_msg_ran[1] == 2);

    mvl_msg_process();                   /* 空队列消费应无副作用 */
    CHECK(s_msg_n == 2);
}

static void test_msg_try_post_full(void)
{
    /* 队列深 4：前 4 条成功，第 5 条失败 */
    for (int i = 0; i < 4; i++) {
        CHECK(mvl_msg_try_post(msg_action, (void *)(intptr_t)(10 + i)));
    }
    CHECK(!mvl_msg_try_post(msg_action, (void *)(intptr_t)99));

    mvl_msg_process();
    CHECK(s_msg_n == 6);                 /* 2 (上个用例) + 4 */
}

/* ---------------------------------------------------------------- mvl_evt */

static int         s_lvgl_cb_n;
static mvl_evt_t   s_lvgl_cb_evt[8];

static void lvgl_cb(const mvl_evt_t *evt)
{
    s_lvgl_cb_evt[s_lvgl_cb_n++] = *evt;   /* 值拷贝留存，验证载荷语义 */
}

static void *s_task_queue;

static void test_evt_subscribe_validation(void)
{
    mvl_evt_init();
    s_task_queue = mvl_port_queue_create(4, sizeof(mvl_evt_t));
    CHECK(s_task_queue != NULL);

    CHECK(!mvl_evt_subscribe(0, lvgl_cb, MVL_EVT_CTX_LVGL, NULL));        /* id 0 保留 */
    CHECK(!mvl_evt_subscribe(MVL_EVT_MAX_ID, lvgl_cb, MVL_EVT_CTX_LVGL, NULL));
    CHECK(!mvl_evt_subscribe(EVT_A, NULL, MVL_EVT_CTX_LVGL, NULL));       /* LVGL 必须给 cb */
    CHECK(!mvl_evt_subscribe(EVT_A, NULL, MVL_EVT_CTX_TASK, NULL));       /* TASK 必须给 queue */
    CHECK(mvl_evt_subscribe(EVT_A, lvgl_cb, MVL_EVT_CTX_LVGL, NULL));
}

static void test_evt_lvgl_routing(void)
{
    mvl_evt_data_t d = { .i32 = 42 };
    CHECK(mvl_evt_publish(EVT_A, &d));
    CHECK(s_lvgl_cb_n == 0);               /* 回调绝不在发布者上下文执行 */

    mvl_msg_process();                     /* LVGL 主任务消费 */
    CHECK(s_lvgl_cb_n == 1);
    CHECK(s_lvgl_cb_evt[0].id == EVT_A);
    CHECK(s_lvgl_cb_evt[0].data.i32 == 42);
}

static void test_evt_payload_value_copy(void)
{
    mvl_evt_data_t d = { .u32 = 7 };
    CHECK(mvl_evt_publish(EVT_A, &d));
    d.u32 = 999;                           /* 发布后立即改原值，订阅者应看到旧值 */

    mvl_msg_process();
    CHECK(s_lvgl_cb_n == 2);
    CHECK(s_lvgl_cb_evt[1].data.u32 == 7);
}

static void test_evt_task_routing(void)
{
    CHECK(mvl_evt_subscribe(EVT_B, NULL, MVL_EVT_CTX_TASK, s_task_queue));

    mvl_evt_data_t d = { .f32 = 1.5f };
    CHECK(mvl_evt_publish(EVT_B, &d));     /* 立即入队，无需 msg 泵 */

    mvl_evt_t evt;
    CHECK(mvl_port_queue_receive(s_task_queue, &evt, 0) == MVL_PORT_OK);
    CHECK(evt.id == EVT_B);
    CHECK(evt.data.f32 == 1.5f);
    /* 队列应已空 */
    CHECK(mvl_port_queue_receive(s_task_queue, &evt, 0) == MVL_PORT_FAIL);
}

static void test_evt_multi_subscribers(void)
{
    /* EVT_C：一个 LVGL 订阅者 + 一个任务订阅者 */
    CHECK(mvl_evt_subscribe(EVT_C, lvgl_cb, MVL_EVT_CTX_LVGL, NULL));
    CHECK(mvl_evt_subscribe(EVT_C, NULL, MVL_EVT_CTX_TASK, s_task_queue));
    /* 超过 MVL_EVT_MAX_SUBS_PER_EVT=2 后应失败 */
    CHECK(!mvl_evt_subscribe(EVT_C, lvgl_cb, MVL_EVT_CTX_LVGL, NULL));

    CHECK(mvl_evt_publish(EVT_C, NULL));   /* NULL 载荷合法（数据走 Model 快照模式） */

    mvl_evt_t evt;
    CHECK(mvl_port_queue_receive(s_task_queue, &evt, 0) == MVL_PORT_OK);
    CHECK(evt.id == EVT_C);

    int before = s_lvgl_cb_n;
    mvl_msg_process();
    CHECK(s_lvgl_cb_n == before + 1);
    CHECK(s_lvgl_cb_evt[before].id == EVT_C);
}

static void test_evt_pool_exhaustion(void)
{
    /* 池深 2：不消费的情况下连续发布 3 个 LVGL 事件，第 3 个应被丢弃 */
    CHECK(mvl_evt_publish(EVT_A, NULL));
    CHECK(mvl_evt_publish(EVT_A, NULL));
    uint32_t drops_before = mvl_evt_drop_count();
    CHECK(mvl_evt_publish(EVT_A, NULL));   /* 池满：返回 true 但计数丢弃 */
    CHECK(mvl_evt_drop_count() == drops_before + 1);

    mvl_msg_process();                     /* 消费后池回收 */
    CHECK(s_lvgl_cb_n == 5);               /* 3(前面用例累计) + 本用例实际投递的 2 */
}

static void test_evt_invalid_publish(void)
{
    CHECK(!mvl_evt_publish(0, NULL));
    CHECK(!mvl_evt_publish(MVL_EVT_MAX_ID, NULL));
}

static void test_evt_task_queue_full_drop(void)
{
    /* 任务订阅队列深 4：灌满后继续发布，应计入丢包而不阻塞发布者 */
    void *q = mvl_port_queue_create(4, sizeof(mvl_evt_t));
    CHECK(q != NULL);
    /* 换一个空闲事件 ID，避免与前面用例互相影响 */
    mvl_evt_id_t id = 10;
    CHECK(mvl_evt_subscribe(id, NULL, MVL_EVT_CTX_TASK, q));

    for (int i = 0; i < 4; i++) CHECK(mvl_evt_publish(id, NULL));
    uint32_t before = mvl_evt_drop_count();
    CHECK(mvl_evt_publish(id, NULL));
    CHECK(mvl_evt_drop_count() == before + 1);
}

/* ------------------------------------------------------- 多线程冒烟测试 */

#define MT_MSG_COUNT 200

static void mt_action(void *ctx)
{
    (void)ctx;
    __sync_fetch_and_add(&s_msg_n, 1);
}

static void *mt_producer(void *arg)
{
    (void)arg;
    for (int i = 0; i < MT_MSG_COUNT; i++) {
        mvl_msg_post(mt_action, NULL);   /* 队列满时阻塞等待消费，不丢消息 */
    }
    return NULL;
}

static void test_msg_multithread(void)
{
    int before = s_msg_n;

    pthread_t th;
    CHECK(pthread_create(&th, NULL, mt_producer, NULL) == 0);

    /* 主线程模拟 LVGL 主任务周期消费 */
    while (__sync_fetch_and_add(&s_msg_n, 0) - before < MT_MSG_COUNT) {
        mvl_msg_process();
        usleep(1000);
    }
    pthread_join(th, NULL);
    CHECK(s_msg_n - before == MT_MSG_COUNT);
}

/* ------------------------------------------------------------------ main */

int main(void)
{
    test_msg_basic();
    test_msg_try_post_full();

    test_evt_subscribe_validation();
    test_evt_lvgl_routing();
    test_evt_payload_value_copy();
    test_evt_task_routing();
    test_evt_multi_subscribers();
    test_evt_pool_exhaustion();
    test_evt_invalid_publish();
    test_evt_task_queue_full_drop();

    test_msg_multithread();

    printf("\n%d checks, %d failed\n", s_checks, s_fails);
    return s_fails == 0 ? 0 : 1;
}
