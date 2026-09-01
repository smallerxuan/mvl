# MVL 文档索引

文档分两类：**设计文档**回答「为什么这样设计」，面向想了解原理、参与开发或评审架构的读者；**用户使用文档**回答「怎么用好它」，面向集成与使用本库的开发者。

## 设计文档（design/）

- [design/design.md](design/design.md) —— 架构设计：LVGL 8.x 线程安全问题、`mvl_msg` / `mvl_evt` 机制原理、单写者原则与 MVVM-Lite 分层模式

## 用户使用文档（user/）

- [user/porting.md](user/porting.md) —— 移植指南：`mvl_port` 接口契约、配置宏、移植到新 RTOS 的步骤
- [user/pitfalls.md](user/pitfalls.md) —— 陷阱合集：真机踩坑记录（现象 → 根因 → 正确做法）

配套阅读：[../tools/README.md](../tools/README.md) —— mvl-gen 代码生成器与 mvl-studio 图形编辑器。
