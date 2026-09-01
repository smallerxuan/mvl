/*
 * demo_wifi —— 后台任务模拟：net_manage 命令消费者 + wifi_scan 生产者
 *
 * net_manage：以 MVL_EVT_CTX_TASK 订阅命令事件，事件直接进自己的队列，
 *             在自己任务上下文消费（执行"驱动"操作）。
 * wifi_scan ：周期产生假扫描结果，经 Model 写状态 + 发事件通知 UI。
 * 两者都不认识 View / LVGL，只与 Model 和事件总线打交道。
 */
#include "demo_model.h"
#include "demo_events.h"

#include <mvl/mvl_evt.h>
#include <mvl/mvl_port.h>

#include <stdio.h>
#include <string.h>
#include <pthread.h>
#include <unistd.h>

static void *s_net_queue;   /* net_manage 任务的事件队列（mvl_evt_t 元素） */

static void do_scan(void)
{
    static const demo_wifi_ap_t fake_aps[] = {
        { "HomeWiFi",   -45 },
        { "CoffeeShop", -67 },
        { "Neighbor5G", -80 },
    };
    demo_model_set_scan_results(fake_aps, 3);
}

static void do_connect(void)
{
    demo_state_t s = demo_model_snapshot();   /* 命令参数经 Model 快照传递 */

    printf("[net_manage] connecting to \"%s\" ...\n", s.pending_ssid);
    demo_model_set_conn_state(DEMO_CONN_CONNECTING);
    usleep(300 * 1000);
    demo_model_set_conn_state(DEMO_CONN_CONNECTED);
}

/* net_manage 任务主循环：从自己的队列取命令事件并执行 */
static void *net_manage_task(void *arg)
{
    (void)arg;

    mvl_evt_t evt;
    while (1) {
        if (mvl_port_queue_receive(s_net_queue, &evt, MVL_PORT_WAIT_FOREVER) != MVL_PORT_OK)
            continue;

        switch (evt.id) {
        case EVT_CMD_WIFI_SCAN:    do_scan();    break;
        case EVT_CMD_WIFI_CONNECT: do_connect(); break;
        default: break;
        }
    }
    return NULL;
}

/* wifi_scan 任务：周期扫描（真实工程里是 wifi 驱动事件回调） */
static void *wifi_scan_task(void *arg)
{
    (void)arg;

    while (1) {
        sleep(2);
        mvl_evt_publish(EVT_CMD_WIFI_SCAN, NULL);  /* 模拟触发 */
    }
    return NULL;
}

void demo_wifi_start(void)
{
    pthread_t th;

    /* 基础设施就绪后再注册订阅（顺序要求见 docs/user/pitfalls.md） */
    s_net_queue = mvl_port_queue_create(8, sizeof(mvl_evt_t));
    mvl_evt_subscribe(EVT_CMD_WIFI_SCAN,    NULL, MVL_EVT_CTX_TASK, s_net_queue);
    mvl_evt_subscribe(EVT_CMD_WIFI_CONNECT, NULL, MVL_EVT_CTX_TASK, s_net_queue);

    pthread_create(&th, NULL, net_manage_task, NULL);
    pthread_detach(th);
    pthread_create(&th, NULL, wifi_scan_task, NULL);
    pthread_detach(th);
}
