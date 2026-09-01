/*
 * demo_vm —— ViewModel：订阅事件，读 Model 快照，驱动 View 接口
 *
 * 所有回调都注册为 MVL_EVT_CTX_LVGL，因此永远运行在 LVGL 主任务上下文，
 * 可以安全调用 View（真实工程里即 lv_*()）。
 */
#include "demo_model.h"
#include "demo_view.h"
#include "demo_events.h"

#include <mvl/mvl_evt.h>

/* 扫描结果更新：数组超过事件 8 字节载荷上限，数据本体读 Model 快照 */
static void on_wifi_scan_updated(const mvl_evt_t *evt)
{
    (void)evt;

    demo_state_t s = demo_model_snapshot();
    demo_view_show_scan_results(s.ap_count, s.aps, s.scan_state);
}

/* 连接状态变更：回显提示 */
static void on_wifi_conn_changed(const mvl_evt_t *evt)
{
    (void)evt;

    demo_state_t s = demo_model_snapshot();
    demo_view_show_conn_state(s.conn_state, s.pending_ssid);
}

void demo_vm_init(void)
{
    mvl_evt_subscribe(EVT_WIFI_SCAN_UPDATED, on_wifi_scan_updated, MVL_EVT_CTX_LVGL, NULL);
    mvl_evt_subscribe(EVT_WIFI_CONN_CHANGED, on_wifi_conn_changed, MVL_EVT_CTX_LVGL, NULL);
}
