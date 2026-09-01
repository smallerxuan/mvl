/*
 * mvl_model —— 状态中心（模板）
 *
 * 系统状态唯一权威数据源。规则只有一条：
 * 状态字段只能通过 set_xxx() 修改——函数内完成「写状态 + 发事件」的绑定，
 * 状态变更必然伴随事件，UI 永不漏刷新；UI 侧只通过 snapshot() 读。
 * 本模块不包含任何 LVGL 调用。
 */
#ifndef _MVL_MODEL_H_
#define _MVL_MODEL_H_

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>

/* ---- Model/View/生产者共享的契约类型（不依赖具体驱动头文件） ---- */
/* typedef struct { ... } app_xxx_t; */

/* 系统状态：全系统唯一权威数据源 */
typedef struct {
    /* <按产品定义状态字段，例：>
       app_xxx_state_t xxx_state;
       uint16_t          xxx_count;
       app_xxx_t         xxx_items[APP_XXX_MAX];
       char              pending_xxx[33];   // 命令参数（配合 EVT_CMD_xxx）
    */
    int _placeholder;   /* 删除本行，替换为上面的字段 */
} mvl_state_t;

void mvl_model_init(void);

/* UI 侧读接口：互斥保护的整体快照，一次拷贝 */
mvl_state_t mvl_model_snapshot(void);

/* 后台侧写接口：写状态 + 自动发布对应事件（每个状态字段一组） */
/* void mvl_model_set_xxx(const app_xxx_t *items, uint16_t count); */

#ifdef __cplusplus
}
#endif

#endif /* _MVL_MODEL_H_ */
