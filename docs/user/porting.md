# MVL 移植指南

*`mvl_port` 移植抽象层接口语义、参考移植对比与新平台移植步骤*

> **配套文档**：[design.md](../design/design.md)（架构设计）· [pitfalls.md](pitfalls.md)（陷阱合集）
> 
> **相关文件**：`include/mvl/mvl_port.h`（接口契约）· `include/mvl/mvl_config.h`（配置宏）· `port/`（三个参考移植）

---

## 1. 移植层在架构中的位置

库本体（`mvl_msg` / `mvl_evt`）**只依赖 `mvl_port.h` 声明的接口**，不直接依赖任何 RTOS API。集成时必须为工程链接**恰好一个**移植实现：

| 移植 | 目标环境 | 一句话说明 |
|------|----------|-----------|
| `port/posix/` | Linux / macOS 主机（pthread） | host 仿真与单元测试，无需硬件即可运行总线逻辑、进 CI |
| `port/freertos/` | vanilla FreeRTOS（非 ESP-IDF） | 无参临界区形式，对应单核或 SMP 之前的经典 API |
| `port/esp_idf/` | ESP-IDF（FreeRTOS SMP） | 持自旋锁临界区，双核间互斥才成立 |

构建形态：

- **ESP-IDF 组件**：仓库根 `CMakeLists.txt` 检测到 `ESP_PLATFORM` 时自动注册 `src/*.c` + `port/esp_idf/mvl_port.c`，无需手工选择；
- **纯 CMake（host）**：默认 `MVL_PORT=posix`，可用 `-DMVL_PORT=freertos` 等切换，或把 `src/mvl_msg.c`、`src/mvl_evt.c` 与你自己的 `mvl_port.c` 直接加入工程构建系统。

移植到其他 RTOS 时，照着 `port/` 下任一参考实现补齐 §2 的全部接口即可。

---

## 2. `mvl_port.h` 接口契约

### 2.1 通用约定

- 返回值：`MVL_PORT_OK`（0）成功 / `MVL_PORT_FAIL`（-1）失败；
- 超时参数单位是**毫秒**（不是 tick），移植层负责换算（FreeRTOS 上用 `pdMS_TO_TICKS()`）；
- 特殊值：`timeout_ms = 0` 不等待；`MVL_PORT_WAIT_FOREVER`（`(uint32_t)-1`）永久阻塞；
- 队列句柄对库不透明，一律以 `void *` 持有，具体类型由移植层自定。

### 2.2 队列（四操作）

```c
void *mvl_port_queue_create(size_t len, size_t item_size);   /* 失败返回 NULL */
int   mvl_port_queue_send(void *q, const void *item, uint32_t timeout_ms);
int   mvl_port_queue_send_isr(void *q, const void *item);    /* 不允许阻塞，满即失败 */
int   mvl_port_queue_receive(void *q, void *item, uint32_t timeout_ms);
```

语义要点：

- 全部按**值拷贝**收发；`create` 的 `len` 是元素个数、`item_size` 是单元素字节数；
- `send`：任务上下文。`timeout_ms` 为 0 时满即失败；为 `MVL_PORT_WAIT_FOREVER` 时必须阻塞到投递成功（`mvl_msg_post()` 的「关键事件不丢」语义依赖这一点）；
- `send_isr`：ISR 上下文。**任何情况下不得阻塞**；队列满返回 `MVL_PORT_FAIL`。FreeRTOS 系实现需在发送后按 `xHigherPriorityTaskWoken` 触发 `portYIELD_FROM_ISR()` 类的调度让位；
- `receive`：任务上下文。收到返回 `MVL_PORT_OK`，超时 / 空返回 `MVL_PORT_FAIL`。

库内使用映射（移植后自检时对照）：

| 库 API | 调用的移植接口 | timeout 参数 |
|--------|---------------|-------------|
| `mvl_msg_init()` | `queue_create(MVL_MSG_QUEUE_DEPTH, sizeof(msg))` | — |
| `mvl_msg_post()` | `queue_send` | `MVL_PORT_WAIT_FOREVER` |
| `mvl_msg_try_post()` | `queue_send` | `0` |
| `mvl_msg_post_isr()` | `queue_send_isr` | — |
| `mvl_msg_process()` | `queue_receive` | `0`（循环取空） |
| `mvl_evt_publish()`（任务订阅者分支） | `queue_send` | `0` |
| `mvl_evt_publish_isr()`（任务订阅者分支） | `queue_send_isr` | — |
| 应用自建 `MVL_EVT_CTX_TASK` 订阅队列 | `queue_create`（元素类型 `mvl_evt_t`）+ 任务内 `queue_receive` | 应用自定 |

### 2.3 临界区（两对）

```c
void mvl_port_critical_enter(void);
void mvl_port_critical_exit(void);
void mvl_port_critical_enter_isr(void);
void mvl_port_critical_exit_isr(void);
```

- **用途**：保护 `mvl_evt` 的 LVGL 投递池等小块共享状态；临界区内的操作只是扫描一个 bool 数组，必须极短；
- **要求**：任务上下文一对、ISR 上下文一对，各自严格配对使用；库不要求可嵌套；
- **单核 vs SMP**：单核平台用关中断或挂起调度器即可；**SMP 平台必须持自旋锁**——只挡本核调度挡不住另一个核同时进入（见 §3.3 与 [pitfalls.md](pitfalls.md) P4）；
- **无状态 enter/exit 的注意事项**：接口是拆开的「进入 / 退出」函数对，无法携带状态。若目标平台的 ISR 临界区 API 采用「进入时返回保存值、退出时回传」的形式（如部分 FreeRTOS 移植的 `taskENTER_CRITICAL_FROM_ISR()` 返回值须传给 `taskEXIT_CRITICAL_FROM_ISR(x)`），移植层需自行安排该值的保存，或改用该平台推荐的等效写法。仓库的 `port/freertos` 参考实现对应经典无参形式，目标 port 在此处编译报错时首先检查这一对函数。

### 2.4 断言

`mvl_port.h` 用 `#ifndef` 提供默认实现：

```c
#ifndef mvl_port_assert
#include <assert.h>
#define mvl_port_assert(x)  assert(x)
#endif
```

- 覆盖方式：在包含 `mvl_port.h` **之前** `#define mvl_port_assert(x)`（如映射到 `configASSERT`）；
- 注意作用域是**每个编译单元**：只在移植层 `mvl_port.c` 里定义，不会影响 `mvl_msg.c` / `mvl_evt.c` 的展开。要全库统一映射，用编译选项（如 `-D'mvl_port_assert(x)=configASSERT(x)'`）或工程级强制包含头；
- 断言用于参数与不变量检查（如 `action != NULL`、队列创建成功），发布构建可将其定义为空。

### 2.5 互斥锁

```c
void *mvl_port_mutex_create(void);   /* 失败返回 NULL */
void  mvl_port_mutex_lock(void *m);
void  mvl_port_mutex_unlock(void *m);
```

- **库本体（`src/`）不依赖这一组接口**；它供 Model 等**模式代码**（`examples/templates/`、`mvl-gen` 生成物）保护状态结构的整体拷贝使用，让模板与生成代码保持平台无关；
- 语义：递归非必需、阻塞式加锁；FreeRTOS 系直接映射 `xSemaphoreCreateMutex` / `xSemaphoreTake(portMAX_DELAY)` / `xSemaphoreGive`；
- 与临界区的分工：临界区护「极短的小块共享状态」（投递池标志位），互斥锁护「可能稍长的状态结构拷贝」；不要拿临界区去实现 Model 锁。

---

## 3. 三个参考移植对比

| 维度 | `port/posix` | `port/freertos` | `port/esp_idf` |
|------|-------------|-----------------|----------------|
| 目标环境 | Linux / macOS 主机 | vanilla FreeRTOS | ESP-IDF（SMP 双核） |
| 队列实现 | pthread 互斥锁 + 条件变量 + 环形缓冲 | `xQueueCreate` 等原生队列 | 同左（ESP-IDF 原生队列） |
| 临界区 | 全局 `pthread_mutex` | 无参 `taskENTER_CRITICAL()` | 持自旋锁 `taskENTER_CRITICAL(&mux)` |
| 互斥锁 | `pthread_mutex` | `xSemaphoreCreateMutex` 族 | 同左（ESP-IDF 原生 mutex） |
| ISR 语义 | 无真实 ISR，`_isr` 退化为任务态非阻塞版本 | `xQueueSendFromISR` + `portYIELD_FROM_ISR`；`FROM_ISR` 无参临界区 | 同左队列 API；`taskENTER_CRITICAL_ISR(&mux)` |
| 断言 | 默认 `assert` | `configASSERT` | `configASSERT` |
| 接入方式 | 纯 CMake 默认（`MVL_PORT=posix`），链接 pthread | `-DMVL_PORT=freertos` 或自行加入工程 | ESP-IDF 组件形态自动启用 |

### 3.1 `port/posix`：没有线程中断语义

主机上没有真正的 ISR：`_isr` 变体**退化**为对应的任务态非阻塞版本（`send_isr` = `send(..., 0)`，`_isr` 临界区 = 同一把全局互斥锁）。这足以让总线逻辑在 host 上跑通并进 CI，但**验证不了 ISR 路径**——目标平台的 ISR 行为必须在真机 / 目标环境单独验证（§6）。

### 3.2 `port/freertos`：无参临界区

对应单核 FreeRTOS 或 SMP 之前的经典 API：`taskENTER_CRITICAL()` 不带参数（实现为关中断 / 挂起调度），`taskENTER_CRITICAL_FROM_ISR()` / `taskEXIT_CRITICAL_FROM_ISR()` 亦按无参形式调用。**直接用在 ESP-IDF 上会编译失败**（`too few arguments to vPortEnterCritical`）——这不是小警告，是在提示你临界区语义根本不成立，见下条。

### 3.3 `port/esp_idf`：SMP 必须持锁

ESP-IDF 的 FreeRTOS 是 SMP 版本，两个核各自独立运行。只关本核中断 / 挂本核调度**挡不住另一个核同时进入临界区**，投递池的 `used` 标志扫描会被真并发撕开，表现为偶发的池状态损坏、堆损坏、随机崩溃。因此临界区必须持 `portMUX_TYPE` 自旋锁：

```c
static portMUX_TYPE s_crit_mux = portMUX_INITIALIZER_UNLOCKED;

void mvl_port_critical_enter(void)      { taskENTER_CRITICAL(&s_crit_mux); }
void mvl_port_critical_exit(void)       { taskEXIT_CRITICAL(&s_crit_mux); }
void mvl_port_critical_enter_isr(void)  { taskENTER_CRITICAL_ISR(&s_crit_mux); }
void mvl_port_critical_exit_isr(void)   { taskEXIT_CRITICAL_ISR(&s_crit_mux); }
```

任务上下文与 ISR 上下文分别用不带 / 带 `_ISR` 后缀的形式，不可混用。

> ESP-IDF 工程的另一个集成差异在**消费点**：LVGL 主循环若由 esp_lvgl_port 托管，无法插入 `mvl_msg_process()`，改用 `lv_timer` 周期分发，见 [design.md](../design/design.md) §6.2。

---

## 4. 移植到新 RTOS：步骤清单

1. **建移植文件**：新建 `port/<平台名>/mvl_port.c`，包含 `mvl/mvl_port.h`；
2. **实现队列四操作**：映射到目标 RTOS 的队列 / 消息邮箱。确认支持：任务上下文带超时阻塞发送、ISR 上下文非阻塞发送、按值拷贝；把毫秒超时换算成平台时间单位；
3. **实现临界区两对**：单核可关中断或挂调度；**SMP 必须自旋锁**；处理 §2.3 的「保存值回传」问题；
4. **实现互斥锁三函数**：映射到目标 RTOS 的 mutex（阻塞式、递归非必需，见 §2.5）；
5. **实现 ISR 变体**：用目标 RTOS 的 `FromISR` 族 API，发送后按平台惯例触发调度让位（yield / switch）；
6. **决定断言映射**：默认 `assert`，或按 §2.4 映射到平台断言（注意编译单元作用域）；
7. **接入构建**：`src/mvl_msg.c` + `src/mvl_evt.c` + 你的 `mvl_port.c` 一起编译；CMake 工程可参考根 `CMakeLists.txt` 的 `MVL_PORT` 变量机制；
8. **host 先行验证**：先用 `port/posix` 在 PC 上跑通 `tests/`（`ctest`）与 `examples/host_sim/`，确认你对 API 的用法理解正确——这步不依赖你的移植；
9. **目标平台最小闭环**：一个普通任务 `mvl_msg_post()`、LVGL 主任务消费（§6 of design.md）、一个真实 ISR 源 `mvl_msg_post_isr()`，三者全通再叠业务。

---

## 5. 配置宏（`mvl_config.h`）

全部带默认值，两种覆盖方式任选：编译命令行 `-DMVL_MSG_QUEUE_DEPTH=32`，或在包含 mvl 头文件之前由工程自行 `#define`。

| 宏 | 默认 | 说明 |
|----|:---:|------|
| `MVL_MSG_QUEUE_DEPTH` | 16 | 消息队列深度（每条 = 函数指针 + ctx 指针）。估算：生产者数 × 单消费周期内最多投递条数；高频场景优先合并降频，而非单纯加深 |
| `MVL_MSG_DISPATCH_PERIOD_MS` | 30 | `lv_timer` 分发周期参考值，最坏消费延迟 ≈ 一个周期。**库本体不依赖它**，仅作为默认值提供给集成者创建分发定时器 |
| `MVL_EVT_MAX_ID` | 128 | 事件 ID 上限（不含）。事件 ID 必须从 1 开始连续编号且小于它 |
| `MVL_EVT_MAX_SUBS_PER_EVT` | 4 | 每个事件的最大订阅者数 |
| `MVL_EVT_LVGL_JOB_POOL_SIZE` | 8 | LVGL 投递池深度 ≈ 单个分发周期内可能积压的 LVGL 事件数上限。池满时事件被丢弃并计入 `mvl_evt_drop_count()` |

**RAM 占用估算**：订阅表 ≈ `MVL_EVT_MAX_ID × MVL_EVT_MAX_SUBS_PER_EVT × sizeof(sub_t)`，默认配置下约 8 KB（32 位平台）。`MVL_EVT_MAX_ID` 是按 ID 直接索引的二维表的第一维，事件 ID 分得越稀疏浪费越大——保持从 1 开始连续编号、按模块小段划分即可。

---

## 6. 移植自检 Checklist

- [ ] 只链接了一个移植实现（重复链接会出现重复定义或隐性问题）
- [ ] `send` 在 `MVL_PORT_WAIT_FOREVER` 下确实永久阻塞；为 0 时确实立即返回
- [ ] `send_isr` 在任何情况下不阻塞；发送成功后触发了平台要求的调度让位
- [ ] SMP 平台临界区持自旋锁，任务 / ISR 两对未混用
- [ ] 毫秒 → tick 换算正确（注意 `pdMS_TO_TICKS` 向下取整，小超时可被舍成 0）
- [ ] 断言映射在**所有**编译单元生效（不只移植层那个 .c）
- [ ] `tests/` + `examples/host_sim/` 在 posix 移植下通过（用法基线）
- [ ] 目标平台最小闭环通过：任务投递、ISR 投递、LVGL 任务消费
- [ ] 压力验证：队列满洪泛 + ISR 高频投递下无崩溃，`mvl_evt_drop_count()` 可观测
