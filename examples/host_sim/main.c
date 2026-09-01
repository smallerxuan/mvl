/*
 * host_sim —— MVL host 仿真示例
 *
 * 在 PC 上演示完整 MVVM 链路（无硬件、无 LVGL 依赖）：
 *
 *   wifi_scan 任务 ──┐                        ┌── ViewModel 回调（LVGL 上下文）
 *                    ├─► Model（状态中心）─► 事件总线 ┤
 *   View 命令 ───────┘                        └── net_manage 任务队列（任务上下文）
 *
 * 「LVGL 主任务」由一个周期调用 mvl_msg_process() 的线程扮演——这正是真实
 * 工程中 lv_timer 周期分发所做的事，语义完全一致。真实 LVGL 工程的接法见
 * docs/design/design.md 与 examples/templates/。
 */
#include "demo_model.h"
#include "demo_vm.h"
#include "demo_view.h"
#include "demo_events.h"

#include <mvl/mvl_msg.h>
#include <mvl/mvl_evt.h>
#include <mvl/mvl_config.h>

#include <stdio.h>
#include <pthread.h>
#include <unistd.h>

void demo_wifi_start(void);

static volatile int s_lvgl_ready = 0;

/* 模拟 LVGL 主任务：周期消费消息队列（= lv_timer 分发角色） */
static void *lvgl_task(void *arg)
{
    (void)arg;

    demo_view_set_lvgl_thread(pthread_self());
    s_lvgl_ready = 1;

    while (1) {
        mvl_msg_process();
        usleep(MVL_MSG_DISPATCH_PERIOD_MS * 1000);
    }
    return NULL;
}

/* 模拟一次用户操作：选中 AP、输入密码、点「连接」（UI → 后台命令） */
static void simulate_user_connect(void)
{
    sleep(3);   /* 等第一轮扫描结果出来 */

    printf("[user] pick AP \"HomeWiFi\", press CONNECT\n");
    demo_model_set_pending_cred("HomeWiFi", "secret123");
    mvl_evt_publish(EVT_CMD_WIFI_CONNECT, NULL);
}

int main(void)
{
    pthread_t th;

    /* 启动顺序（陷阱见 docs/user/pitfalls.md）：基础设施 init → 订阅注册 → 业务启动 */
    mvl_msg_init();
    mvl_evt_init();
    demo_model_init();

    pthread_create(&th, NULL, lvgl_task, NULL);
    pthread_detach(th);
    while (!s_lvgl_ready) usleep(1000);

    demo_vm_init();        /* ViewModel 订阅（LVGL 上下文） */
    demo_wifi_start();     /* 后台任务 + 任务上下文订阅 */

    simulate_user_connect();

    sleep(5);              /* 再跑几轮扫描后退出 */
    printf("[main] drop count = %u (正常应为 0)\n", mvl_evt_drop_count());
    return 0;
}
