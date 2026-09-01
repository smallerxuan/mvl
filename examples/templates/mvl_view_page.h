/*
 * mvl_view_<page> —— <页面名> View 接口层（模板）
 *
 * 本页面唯一认识 UI 控件（lv_* / GUI Guider 生成物）的手写文件；
 * 接口只允许在 LVGL 主任务上下文调用（经 mvl_vm / mvl_msg 调度）。
 * View 只做「显示」与「采集用户输入」，不做业务判断。
 */
#ifndef _MVL_VIEW_<PAGE>_H_
#define _MVL_VIEW_<PAGE>_H_

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include "mvl_model.h"   /* View 与 Model 共享的契约类型 */

/* ---- 显示接口（ViewModel 回调内调用） ----
   void mvl_view_<page>_show_xxx(uint16_t count, const app_xxx_t *items, ...);
*/

/* ---- 输入采集接口（UI 事件回调 / 业务侧调用） ----
   const char *mvl_view_<page>_get_selected_xxx(void);
*/

#ifdef __cplusplus
}
#endif

#endif /* _MVL_VIEW_<PAGE>_H_ */
