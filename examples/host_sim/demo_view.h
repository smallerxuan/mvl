/*
 * demo_view —— View 接口层（MVVM 中的 View）
 *
 * 真实工程中这里是唯一调用 lv_*() 的手写文件（操作 GUI Guider 生成的控件）；
 * host 仿真用 printf 代替，并打印执行线程名以验证「View 只在 LVGL 主任务运行」。
 * 接口只允许在 LVGL 主任务上下文调用（经 demo_vm / mvl_msg 调度）。
 */
#ifndef _DEMO_VIEW_H_
#define _DEMO_VIEW_H_

#include <stdint.h>
#include <pthread.h>
#include "demo_model.h"   /* 共享契约类型 */

/* 记录 LVGL 主任务线程句柄，用于打印执行上下文 */
void demo_view_set_lvgl_thread(pthread_t tid);

/* 展示扫描结果 */
void demo_view_show_scan_results(uint16_t count, const demo_wifi_ap_t *aps,
                                 demo_scan_state_t state);

/* 展示连接状态，ssid 用于成功时的回显 */
void demo_view_show_conn_state(demo_conn_state_t state, const char *ssid);

#endif /* _DEMO_VIEW_H_ */
