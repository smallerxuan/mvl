/*
 * mvl_vm —— ViewModel（模板）
 *
 * 订阅事件 → 读 Model 快照 → 调 View 接口。
 * 回调一律注册为 MVL_EVT_CTX_LVGL，永远运行在 LVGL 主任务上下文，
 * 可以安全调用 View（即 lv_*()）。全部订阅在启动期一次注册完毕。
 */
#ifndef _MVL_VM_H_
#define _MVL_VM_H_

#ifdef __cplusplus
extern "C" {
#endif

/* 注册全部 ViewModel 订阅（须在事件可能到达之前调用） */
void mvl_vm_init(void);

#ifdef __cplusplus
}
#endif

#endif /* _MVL_VM_H_ */
