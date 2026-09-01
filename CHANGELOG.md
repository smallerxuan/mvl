# Changelog

本项目遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [0.1.0] - 2026-09-01

首个公开版本。

### Added
- `mvl_msg`：LVGL 8.x 线程安全消息队列（阻塞/非阻塞/ISR 三种投递，单写者消费）
- `mvl_evt`：事件总线（LVGL / 任务两种订阅上下文、8 字节值拷贝载荷、
  LVGL 投递池、`mvl_evt_drop_count()` 丢包观测）
- `mvl_port.h` 移植抽象层 + 三个参考移植：`port/posix`、`port/freertos`、`port/esp_idf`（SMP 持锁临界区）
- `examples/host_sim`：PC 上无硬件跑通完整 MVVM 链路
- `examples/templates`：Model / ViewModel / View 骨架模板与事件表模板
- `tools/mvl-gen`：YAML 接线描述 → 骨架代码生成 CLI（含设计时静态检查与 mermaid 接线图导出）
- `tools/mvl-studio`：图形化接线设计编辑器（PySide6，可选依赖 `[gui]`）——
  树 + 表单/表格编辑 YAML 接线描述，实时 C1~C8 静态检查并定位节点，
  一键调用代码生成；附 `examples/mvl_project.template.yaml` 注释模板
- host 单元测试（总线路由 / 投递池 / 丢包计数 / 多线程冒烟）+ GitHub Actions CI
