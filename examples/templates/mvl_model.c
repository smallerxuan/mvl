/*
 * mvl_model.c —— 状态中心实现（模板）
 *
 * 互斥锁走移植层 mvl_port_mutex_*（库自带的模式代码辅助接口），
 * 本文件因此是平台无关的，可原样用于任何已完成移植的工程。
 */
#include "mvl_model.h"
#include "app_events.h"

#include <mvl/mvl_evt.h>
#include <mvl/mvl_port.h>

#include <string.h>

static mvl_state_t  s_state;
static void        *s_lock;

void mvl_model_init(void)
{
    s_lock = mvl_port_mutex_create();
    mvl_port_assert(s_lock != NULL);

    memset(&s_state, 0, sizeof(s_state));
}

mvl_state_t mvl_model_snapshot(void)
{
    mvl_state_t copy;

    mvl_port_mutex_lock(s_lock);
    copy = s_state;
    mvl_port_mutex_unlock(s_lock);
    return copy;
}

/* ---- 写接口范式：互斥写状态 → 出锁 → 发布事件 ----
   「先写后发」：订阅者读到事件时，快照必已是新值。

void mvl_model_set_xxx(const app_xxx_t *items, uint16_t count)
{
    mvl_port_mutex_lock(s_lock);
    // ... 校验并拷贝进 s_state ...
    mvl_port_mutex_unlock(s_lock);

    mvl_evt_publish(EVT_XXX_UPDATED, NULL);   // 大数据走「事件 + 快照」，载荷为空
}
*/

/* ---- 命令参数字段范式：只写状态不发布事件，命令由 View 另行发布 ----
void mvl_model_set_pending_xxx(const char *arg)
{
    mvl_port_mutex_lock(s_lock);
    // ... strncpy 进 s_state.pending_xxx ...
    mvl_port_mutex_unlock(s_lock);
    // 不发布：消费方在收到 EVT_CMD_xxx 后自行 snapshot() 取参数
}
*/
