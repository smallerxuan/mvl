#include "demo_view.h"

#include <stdio.h>

static pthread_t s_lvgl_tid;

void demo_view_set_lvgl_thread(pthread_t tid)
{
    s_lvgl_tid = tid;
}

static const char *whereami(void)
{
    /* 验证单写者原则：View 必须运行在「LVGL 主任务」线程 */
    return pthread_equal(pthread_self(), s_lvgl_tid) ? "LVGL-task" : "!!WRONG-CONTEXT!!";
}

void demo_view_show_scan_results(uint16_t count, const demo_wifi_ap_t *aps,
                                 demo_scan_state_t state)
{
    if (state == DEMO_SCAN_FAILED) {
        printf("[UI|%s] scan failed\n", whereami());
        return;
    }
    printf("[UI|%s] scan done, %d APs:\n", whereami(), count);
    for (uint16_t i = 0; i < count; i++) {
        printf("[UI|%s]   %-20s rssi=%d\n", whereami(), aps[i].ssid, aps[i].rssi);
    }
}

void demo_view_show_conn_state(demo_conn_state_t state, const char *ssid)
{
    const char *txt = "idle";
    switch (state) {
    case DEMO_CONN_CONNECTING: txt = "connecting"; break;
    case DEMO_CONN_CONNECTED:  txt = "connected";  break;
    case DEMO_CONN_FAILED:     txt = "failed";     break;
    default: break;
    }
    printf("[UI|%s] conn state: %s (%s)\n", whereami(), txt, ssid);
}
