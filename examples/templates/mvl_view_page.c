/*
 * mvl_view_<page>.c —— <页面名> View 接口实现（模板）
 *
 * 唯一允许 include GUI Guider 生成头文件（gui_guider.h 等）的 MVL 手写文件。
 */
#include "mvl_view_<page>.h"

/* #include "gui_guider.h"   // UI 控件生成物，仅本层可见 */

/* extern lv_ui guider_ui;   // GUI Guider 全局 UI 结构 */

/* ---- 显示接口实现范式 ----
void mvl_view_<page>_show_xxx(uint16_t count, const app_xxx_t *items, ...)
{
    // 直接操作本页控件：lv_table_set_cell_value(...) / lv_label_set_text(...) ...
    // 本函数运行在 LVGL 主任务上下文，可安全调用任何 lv_* API
}
*/

/* ---- 输入采集实现范式 ----
const char *mvl_view_<page>_get_selected_xxx(void)
{
    // return lv_dropdown_get_selected_str(...) 之类
}
*/
