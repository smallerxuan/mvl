#include "demo_model.h"
#include "demo_events.h"

#include <mvl/mvl_evt.h>
#include <mvl/mvl_port.h>

#include <string.h>

static demo_state_t  s_state;
static void         *s_lock;

void demo_model_init(void)
{
    s_lock = mvl_port_mutex_create();

    mvl_port_mutex_lock(s_lock);
    memset(&s_state, 0, sizeof(s_state));
    mvl_port_mutex_unlock(s_lock);
}

demo_state_t demo_model_snapshot(void)
{
    demo_state_t copy;

    mvl_port_mutex_lock(s_lock);
    copy = s_state;
    mvl_port_mutex_unlock(s_lock);
    return copy;
}

void demo_model_set_scan_results(const demo_wifi_ap_t *aps, uint16_t count)
{
    mvl_port_mutex_lock(s_lock);
    if (count > DEMO_WIFI_AP_MAX) {
        count = DEMO_WIFI_AP_MAX;
    }
    s_state.ap_count = count;
    if (count > 0 && aps != NULL) {
        memcpy(s_state.aps, aps, sizeof(demo_wifi_ap_t) * count);
    }
    s_state.scan_state = DEMO_SCAN_DONE;
    mvl_port_mutex_unlock(s_lock);

    /* 先写后发：订阅者读到事件时，快照必已是新值 */
    mvl_evt_publish(EVT_WIFI_SCAN_UPDATED, NULL);
}

void demo_model_set_pending_cred(const char *ssid, const char *password)
{
    mvl_port_mutex_lock(s_lock);
    memset(s_state.pending_ssid, 0, sizeof(s_state.pending_ssid));
    memset(s_state.pending_password, 0, sizeof(s_state.pending_password));
    if (ssid != NULL) {
        strncpy(s_state.pending_ssid, ssid, sizeof(s_state.pending_ssid) - 1);
    }
    if (password != NULL) {
        strncpy(s_state.pending_password, password, sizeof(s_state.pending_password) - 1);
    }
    mvl_port_mutex_unlock(s_lock);
    /* 只写状态不发布事件：连接命令由 View 另行发布 EVT_CMD_WIFI_CONNECT */
}

void demo_model_set_conn_state(demo_conn_state_t state)
{
    mvl_port_mutex_lock(s_lock);
    s_state.conn_state = state;
    mvl_port_mutex_unlock(s_lock);

    mvl_evt_publish(EVT_WIFI_CONN_CHANGED, NULL);
}
