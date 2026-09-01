# 单元测试：直接以小组配置编译库源码，便于构造池满/队列满等边界场景
add_executable(test_mvl
    test_mvl.c
    ${CMAKE_SOURCE_DIR}/src/mvl_msg.c
    ${CMAKE_SOURCE_DIR}/src/mvl_evt.c
    ${CMAKE_SOURCE_DIR}/port/posix/mvl_port.c
)
target_include_directories(test_mvl PRIVATE ${CMAKE_SOURCE_DIR}/include)
target_compile_definitions(test_mvl PRIVATE
    MVL_MSG_QUEUE_DEPTH=4
    MVL_EVT_MAX_ID=64
    MVL_EVT_MAX_SUBS_PER_EVT=2
    MVL_EVT_LVGL_JOB_POOL_SIZE=2
)
find_package(Threads REQUIRED)
target_link_libraries(test_mvl PRIVATE Threads::Threads)

add_test(NAME mvl_unit COMMAND test_mvl)
