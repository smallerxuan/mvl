/*
 * mvl_vm.c —— ViewModel 实现（模板）
 */
#include "mvl_vm.h"
#include "mvl_model.h"
#include "app_events.h"
/* #include "mvl_view_<page>.h"   // 各页面 View 接口 */

#include <mvl/mvl_evt.h>

#include <stddef.h>

/* ---- 回调范式：读快照 → 调 View 接口 ----
   事件载荷超过 8 字节时，数据本体一律走 Model 快照（见 docs/design/design.md）。

static void on_xxx_updated(const mvl_evt_t *evt)
{
    (void)evt;

    mvl_state_t s = mvl_model_snapshot();
    mvl_view_<page>_show_xxx(s.xxx_count, s.xxx_items, s.xxx_state);
}
*/

void mvl_vm_init(void)
{
    /* 范式：
       mvl_evt_subscribe(EVT_XXX_UPDATED, on_xxx_updated, MVL_EVT_CTX_LVGL, NULL);
    */
}
