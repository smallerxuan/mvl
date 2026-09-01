# host_sim：在 PC 上跑通 MVL 全链路（无硬件、无 LVGL 依赖）
#
# 用一个周期调用 mvl_msg_process() 的线程模拟「LVGL 主任务」，
# 语义与真实工程中 lv_timer 周期分发完全一致。
add_executable(host_sim
    main.c
    demo_model.c
    demo_vm.c
    demo_view.c
    demo_wifi.c
)
target_link_libraries(host_sim PRIVATE mvl)
