/*
 * demo_model —— 状态中心（MVVM 中的 Model）
 *
 * 系统状态唯一权威数据源。规则只有一条：
 * 状态字段只能通过 set_xxx() 修改——函数内完成「写状态 + 发事件」的绑定，
 * 状态变更必然伴随事件，UI 永不漏刷新；UI 侧只通过 snapshot() 读。
 * 本模块不包含任何 LVGL 调用。
 */
#ifndef _DEMO_MODEL_H_
#define _DEMO_MODEL_H_

#include <stdint.h>

#define DEMO_WIFI_AP_MAX   10

/* WiFi 条目：Model/View/生产者共享的契约类型 */
typedef struct {
    char    ssid[33];
    int8_t  rssi;
} demo_wifi_ap_t;

typedef enum {
    DEMO_SCAN_IDLE = 0,
    DEMO_SCAN_DONE,
    DEMO_SCAN_FAILED,
} demo_scan_state_t;

typedef enum {
    DEMO_CONN_IDLE = 0,
    DEMO_CONN_CONNECTING,
    DEMO_CONN_CONNECTED,
    DEMO_CONN_FAILED,
} demo_conn_state_t;

/* 系统状态：全系统唯一权威数据源 */
typedef struct {
    demo_scan_state_t scan_state;
    uint16_t          ap_count;
    demo_wifi_ap_t    aps[DEMO_WIFI_AP_MAX];
    char              pending_ssid[33];      /* 待连接凭据（配合 EVT_CMD_WIFI_CONNECT） */
    char              pending_password[65];
    demo_conn_state_t conn_state;            /* 连接状态（配合 EVT_WIFI_CONN_CHANGED） */
} demo_state_t;

void demo_model_init(void);

/* UI 侧读接口：互斥保护的整体快照，一次拷贝 */
demo_state_t demo_model_snapshot(void);

/* 后台侧写接口：写状态 + 自动发布对应事件 */
void demo_model_set_scan_results(const demo_wifi_ap_t *aps, uint16_t count);
void demo_model_set_conn_state(demo_conn_state_t state);

/* 写入待连接凭据（只写状态不发布事件；连接命令由 View 另行发布） */
void demo_model_set_pending_cred(const char *ssid, const char *password);

#endif /* _DEMO_MODEL_H_ */
