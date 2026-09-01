# ============================================================================
# MVL (MVVM-Lite) —— 适用于 LVGL 8.x 多任务系统的轻量 MVVM 支持库
#
# 两种构建形态：
#   1. ESP-IDF 组件：放入工程的 components/ 目录即可，
#      自动注册源文件并启用 port/esp_idf 移植层；
#   2. 纯 CMake（host）：cmake -B build && cmake --build build
#      默认启用 port/posix 移植层，构建静态库 + 单元测试 + host_sim 示例。
# ============================================================================

# ---- ESP-IDF 组件形态 ----
if(ESP_PLATFORM)
    idf_component_register(
        SRCS "src/mvl_msg.c" "src/mvl_evt.c" "port/esp_idf/mvl_port.c"
        INCLUDE_DIRS "include"
    )
    return()
endif()

# ---- 纯 CMake（host）形态 ----
cmake_minimum_required(VERSION 3.13)
project(mvl C)

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)

if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Debug)
endif()

add_compile_options(-Wall -Wextra)

# 移植层选择：posix（默认，host 用）/ 其他移植由集成者自行加入工程
set(MVL_PORT "posix" CACHE STRING "移植层目录名（port/ 下）")

add_library(mvl STATIC
    src/mvl_msg.c
    src/mvl_evt.c
    port/${MVL_PORT}/mvl_port.c
)
target_include_directories(mvl PUBLIC include)

if(MVL_PORT STREQUAL "posix")
    find_package(Threads REQUIRED)
    target_link_libraries(mvl PUBLIC Threads::Threads)
endif()

# 单元测试（host）
option(MVL_BUILD_TESTS "构建单元测试" ON)
if(MVL_BUILD_TESTS)
    enable_testing()
    add_subdirectory(tests)
endif()

# host 仿真示例
option(MVL_BUILD_EXAMPLES "构建 host_sim 示例" ON)
if(MVL_BUILD_EXAMPLES)
    add_subdirectory(examples/host_sim)
endif()
