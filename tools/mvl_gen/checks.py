"""checks.py —— 设计时静态检查（规则依据见 ../docs/design/design.md 与 ../docs/user/pitfalls.md）。

实现规则：C1 / C2 / C3 / C4 / C7 / C8。
C5（set_xxx 写状态但未发布事件）与 C6（基础设施 init 先于订阅注册）由生成器
构造上保证——生成代码天然满足，检查器无需再验（见 codegen.py 模板）。
"""

from collections import Counter, namedtuple

# MVL_EVT_MAX_ID 默认值（mvl_config.h），事件 ID 必须小于它
MVL_EVT_MAX_ID_DEFAULT = 128

Issue = namedtuple("Issue", ["rule", "level", "message"])

ERROR = "错误"
WARNING = "警告"


def run_checks(ir):
    """对 IR 执行全部静态检查，返回 Issue 列表（先错误后警告之外的排序不做）。"""
    issues = []
    issues += _check_c1_lvgl_to_lvgl(ir)
    issues += _check_c2_c7_payload(ir)
    issues += _check_c3_isr(ir)
    issues += _check_c4_hygiene(ir)
    issues += _check_c8_collisions(ir)
    return issues


def has_errors(issues):
    return any(i.level == ERROR for i in issues)


def _check_c1_lvgl_to_lvgl(ir):
    """C1：发布者上下文 = LVGL 且订阅者上下文 = LVGL → 自我死锁风险（错误）。

    依据 docs/user/pitfalls.md P1/P2：LVGL 任务发布的事件若再投递回 LVGL 订阅者，
    等效于 UI 线程给自己发消息，应直接同步调用而非走事件总线。
    """
    issues = []
    for evt in ir["events"]:
        pubs = [p for p in evt["publishers"] if p["context"] == "lvgl"]
        subs = [s for s in evt["subscribers"] if s["context"] == "lvgl"]
        for p in pubs:
            for s in subs:
                target = s.get("handler", s.get("task"))
                issues.append(Issue(
                    "C1", ERROR,
                    f"事件 {evt['id']}：发布者 {p['module']}(lvgl) → 订阅者 "
                    f"{target}(lvgl)，LVGL→LVGL 组合有自我死锁风险；"
                    f"LVGL 上下文内应直接调用，不要走事件总线"))
    return issues


def _check_c2_c7_payload(ir):
    """C2：载荷 > 8 字节（错误）；C7：载荷含指针类型（错误）。依据 docs/user/pitfalls.md P7。"""
    issues = []
    for evt in ir["events"]:
        payload = evt.get("payload")
        if payload is None or str(payload).strip().lower() in ("none", ""):
            continue
        if evt["payload_is_pointer"]:
            issues.append(Issue(
                "C7", ERROR,
                f"事件 {evt['id']}：载荷 '{payload}' 含指针类型；事件载荷为"
                f" 8 字节值拷贝，指针生命周期无法保证——大数据请用"
                f"「就绪事件 + Model 快照」模式"))
        if not evt["payload_known"]:
            issues.append(Issue(
                "C2", WARNING,
                f"事件 {evt['id']}：载荷类型 '{payload}' 无法估算尺寸，"
                f"请确认 sizeof({payload}) <= 8"))
        elif evt["payload_size"] > 8:
            issues.append(Issue(
                "C2", ERROR,
                f"事件 {evt['id']}：载荷 '{payload}' 约 {evt['payload_size']}"
                f" 字节，超过 8 字节上限——大数据请用「就绪事件 + Model 快照」模式"))
    return issues


def _check_c3_isr(ir):
    """C3：ISR 发布者路径检查（错误）。依据 docs/design/design.md §4（投递池）与 docs/user/pitfalls.md P9。

    - ISR 发布的事件若有 LVGL 订阅者，必须在 YAML config.lvgl_job_pool
      显式配置投递池深度（对应 MVL_EVT_LVGL_JOB_POOL_SIZE），否则池深
      未经验证，运行期可能丢事件。
    - 「ISR 发布走 mvl_evt_publish_isr 而非 mvl_evt_publish」由生成器
      在任务侧骨架中构造保证（见 codegen），此处不再重复校验。
    """
    issues = []
    pool = (ir["config"] or {}).get("lvgl_job_pool")
    for evt in ir["events"]:
        isr_pubs = [p for p in evt["publishers"] if p["context"] == "isr"]
        if not isr_pubs:
            continue
        lvgl_subs = [s for s in evt["subscribers"] if s["context"] == "lvgl"]
        if lvgl_subs and not pool:
            issues.append(Issue(
                "C3", ERROR,
                f"事件 {evt['id']}：ISR 发布（{isr_pubs[0]['module']}）且有 "
                f"LVGL 订阅者，但未在 YAML config.lvgl_job_pool 配置 LVGL "
                f"投递池深度——请按单个分发周期内最大积压数显式配置"))
    return issues


def _check_c4_hygiene(ir):
    """C4：工程卫生（警告）。

    - 有事件无订阅者 / 有事件无发布者；
    - Model 字段无人读写（既不出现在任何 setter 的 args/注释关联，也不出现在
      任何 View 接口签名或事件发布链路中——按名称词干近似匹配）。
    """
    issues = []
    for evt in ir["events"]:
        if not evt["subscribers"]:
            issues.append(Issue(
                "C4", WARNING, f"事件 {evt['id']} 没有任何订阅者"))
        if not evt["publishers"]:
            issues.append(Issue(
                "C4", WARNING, f"事件 {evt['id']} 没有任何发布者"))

    # Model 字段引用分析：收集全部可能出现字段名的文本
    haystacks = []
    for st in ir["setters"]:
        haystacks.append(st.get("name", ""))
        haystacks.append(st.get("args", ""))
        haystacks.append(st.get("doc", "") or "")
    for page in ir["view_interfaces"]:
        for fn in page["functions"]:
            haystacks.append(fn.get("args", ""))
            haystacks.append(fn.get("returns", ""))
            haystacks.append(fn.get("doc", "") or "")
    for evt in ir["events"]:
        haystacks.append(evt.get("doc", "") or "")
    blob = "\n".join(str(h) for h in haystacks)

    for field in ir["model"]:
        name = field["name"]
        # 字段名、去前缀词干（wifi_aps → aps）、末位词（wifi_pending_ssid → ssid）
        # 任一被引用即视为有人用
        stems = {name, name.split("_")[-1]}
        for prefix in ("wifi_", "sys_", "ui_"):
            if name.startswith(prefix):
                stems.add(name[len(prefix):])
        if not any(len(stem) >= 3 and stem in blob for stem in stems):
            issues.append(Issue(
                "C4", WARNING,
                f"Model 字段 {name} 疑似无人读写（未出现在任何 setter / "
                f"View 接口 / 事件说明中）"))
    return issues


def _check_c8_collisions(ir):
    """C8：事件 ID 撞号或越段 / View 接口签名重复（错误）。"""
    issues = []

    # 事件 ID 撞号
    by_value = Counter(e["value"] for e in ir["events"])
    for value, count in by_value.items():
        if count > 1:
            names = [e["id"] for e in ir["events"] if e["value"] == value]
            issues.append(Issue(
                "C8", ERROR,
                f"事件 ID 撞号：{', '.join(names)} 同为 {value}"))

    # 事件 ID 越段：越过下一个已用分段基址，或超出 MVL_EVT_MAX_ID
    segs = sorted({e["segment"] for e in ir["events"]})
    for evt in ir["events"]:
        higher = [s for s in segs if s > evt["segment"]]
        if higher and evt["value"] >= higher[0]:
            issues.append(Issue(
                "C8", ERROR,
                f"事件 {evt['id']} = {evt['value']} 越段：越过下一分段基址 "
                f"{higher[0]}（本段基址 {evt['segment']}）"))
        if evt["value"] <= 0 or evt["value"] >= MVL_EVT_MAX_ID_DEFAULT:
            issues.append(Issue(
                "C8", ERROR,
                f"事件 {evt['id']} = {evt['value']} 超出合法范围 "
                f"[1, {MVL_EVT_MAX_ID_DEFAULT})（MVL_EVT_MAX_ID）"))

    # 事件重名
    by_id = Counter(e["id"] for e in ir["events"])
    for eid, count in by_id.items():
        if count > 1:
            issues.append(Issue("C8", ERROR, f"事件名 {eid} 重复定义"))

    # View 接口签名重复（同页面内同名函数）
    for page in ir["view_interfaces"]:
        by_name = Counter(fn["name"] for fn in page["functions"])
        for name, count in by_name.items():
            if count > 1:
                issues.append(Issue(
                    "C8", ERROR,
                    f"页面 {page['page']} 的 View 接口 {name} 重复定义"))

    # setter 引用了未定义事件（订阅了未定义事件的镜像问题）
    evt_ids = {e["id"] for e in ir["events"]}
    for st in ir["setters"]:
        if st.get("event") and st["event"] not in evt_ids:
            issues.append(Issue(
                "C4", WARNING,
                f"setter mvl_model_set_{st['name']} 发布了未定义事件 {st['event']}"))
    return issues


def format_issues(issues):
    """格式化为 CLI 输出文本。"""
    lines = []
    for i in issues:
        lines.append(f"[{i.rule}] {i.level}: {i.message}")
    return "\n".join(lines)
