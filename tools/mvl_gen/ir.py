"""ir.py —— YAML 加载与中间表示（IR）规范化。

YAML schema：

    project: wifi_demo
    mvl_version: 0.1.0

    types: |                      # 可选：Model/View/生产者共享契约类型的原始 C 片段
      ...                         #       原样插入 mvl_model.h（typedef/enum/#define）

    model:                        # mvl_state_t 的字段
      - { name: wifi_ap_count, type: uint16_t, doc: 扫描到的 AP 数 }

    setters:                      # 可选：Model 写接口 mvl_model_set_<name>()
      - name: wifi_conn_state
        args: "mvl_wifi_conn_state_t state"
        event: EVT_WIFI_CONN_CHANGED   # 写后自动发布；省略 = 只写不发
        doc: 更新连接状态

    events:
      - id: EVT_WIFI_SCAN_UPDATED
        segment: 32               # 所属分段基址；同段内按声明顺序自动编号
        value: 32                 # 可选：显式指定数值（缺省自动分配）
        payload: none             # none 或 C 类型（<= 8 字节、不得含指针）
        doc: 扫描结果已更新
        publishers:
          - { module: wifi_scan, context: sys_evt }
        subscribers:
          - { handler: on_wifi_scan_updated, context: lvgl }   # ViewModel 回调
          - { task: net_manage, context: task_queue }          # 任务队列消费

    view_interfaces:
      - page: wifi
        functions:
          - { name: show_conn_state, args: "mvl_wifi_conn_state_t state", returns: void }

    config:                       # 可选：与 mvl_config.h 对应的应用配置（静态检查用）
      lvgl_job_pool: 8            # LVGL 投递池深度（C3 检查依据）

执行上下文词表：
  发布者 context: lvgl / task / sys_evt / isr
  订阅者 context: lvgl（ViewModel 回调）/ task_queue（任务队列）
"""

import re

import yaml


class IrError(Exception):
    """YAML 结构非法（连静态检查都无法进行）时抛出。"""


# ---- 载荷类型尺寸估算（C2 检查用，仅覆盖常见定长类型） ----
_BASE_TYPE_SIZES = {
    "char": 1, "signed char": 1, "unsigned char": 1,
    "int8_t": 1, "uint8_t": 1, "bool": 1,
    "int16_t": 2, "uint16_t": 2, "short": 2, "unsigned short": 2,
    "int32_t": 4, "uint32_t": 4, "int": 4, "unsigned int": 4,
    "float": 4, "int64_t": 8, "uint64_t": 8, "double": 8,
}

_ARRAY_RE = re.compile(r"^(?P<base>.+?)\s*\[\s*(?P<n>\d+)\s*\]$")

# 合法上下文词表
PUB_CONTEXTS = ("lvgl", "task", "sys_evt", "isr")
SUB_CONTEXTS = ("lvgl", "task_queue")


def _field_decl(c_type, name):
    """把 YAML 类型写法渲染成 C 字段声明，如
    ("mvl_wifi_ap_t[10]", "wifi_aps") -> "mvl_wifi_ap_t wifi_aps[10];"
    """
    m = _ARRAY_RE.match(c_type)
    if m:
        return f"{m.group('base').strip()} {name}[{m.group('n')}];"
    return f"{c_type} {name};"


def payload_size(payload):
    """估算载荷字节数。

    返回 (size, known)：known=False 表示类型无法识别（按警告处理）。
    payload 为 none/空 时返回 (0, True)。
    """
    if payload is None:
        return 0, True
    if isinstance(payload, dict):
        payload = payload.get("type", "none")
    text = str(payload).strip()
    if text.lower() in ("none", "void", ""):
        return 0, True
    m = _ARRAY_RE.match(text)
    count = 1
    base = text
    if m:
        base = m.group("base").strip()
        count = int(m.group("n"))
    base = re.sub(r"\bconst\b", "", base).strip()
    if base in _BASE_TYPE_SIZES:
        return _BASE_TYPE_SIZES[base] * count, True
    return 0, False


def payload_has_pointer(payload):
    """C7：载荷是否含指针类型。"""
    if payload is None:
        return False
    if isinstance(payload, dict):
        payload = payload.get("type", "none")
    return "*" in str(payload)


def _expect_list(node, key):
    value = node.get(key) or []
    if not isinstance(value, list):
        raise IrError(f"字段 '{key}' 必须是列表")
    return value


def load_ir(path):
    """加载 YAML 文件并规范化为 IR dict（详见 load_ir_text）。"""
    with open(path, "r", encoding="utf-8") as f:
        return load_ir_text(f.read())


def load_ir_text(text):
    """从 YAML 文本加载并规范化为 IR dict（供 mvl-studio 等内存场景复用）。

    规范化内容：
      - 事件按 segment 分组、段内按声明顺序自动分配数值 ID（显式 value 优先）；
      - 每个事件计算 payload_size / payload_known；
      - 收集 task 订阅者列表（任务骨架生成用）。
    """
    raw = yaml.safe_load(text)
    if not isinstance(raw, dict):
        raise IrError("YAML 顶层必须是 mapping")

    project = raw.get("project")
    if not project:
        raise IrError("缺少必填字段 'project'")

    ir = {
        "project": str(project),
        "mvl_version": str(raw.get("mvl_version", "")),
        "types": raw.get("types") or "",
        "config": raw.get("config") or {},
        "model": _expect_list(raw, "model"),
        "setters": _expect_list(raw, "setters"),
        "events": _expect_list(raw, "events"),
        "view_interfaces": _expect_list(raw, "view_interfaces"),
    }

    for field in ir["model"]:
        if "name" not in field or "type" not in field:
            raise IrError("model 字段必须包含 name 和 type")
        field.setdefault("doc", "")
        field["decl"] = _field_decl(str(field["type"]), str(field["name"]))

    for st in ir["setters"]:
        if "name" not in st:
            raise IrError("setters 项必须包含 name")
        st.setdefault("args", "void")
        st.setdefault("event", None)
        st.setdefault("doc", "")

    # ---- 事件 ID 分配：按 segment 分组，段内顺序编号 ----
    seg_next = {}
    for evt in ir["events"]:
        if "id" not in evt:
            raise IrError("events 项必须包含 id")
        if "segment" not in evt:
            raise IrError(f"事件 {evt['id']} 缺少 segment")
        seg = int(evt["segment"])
        evt["segment"] = seg
        if "value" in evt and evt["value"] is not None:
            evt["value"] = int(evt["value"])
            seg_next[seg] = max(seg_next.get(seg, seg), evt["value"] + 1)
        else:
            evt["value"] = seg_next.get(seg, seg)
            seg_next[seg] = evt["value"] + 1
        size, known = payload_size(evt.get("payload"))
        evt["payload_size"] = size
        evt["payload_known"] = known
        evt["payload_is_pointer"] = payload_has_pointer(evt.get("payload"))
        evt["publishers"] = _expect_list(evt, "publishers")
        evt["subscribers"] = _expect_list(evt, "subscribers")
        evt.setdefault("doc", "")
        evt.setdefault("payload", None)
        for pub in evt["publishers"]:
            if "module" not in pub:
                raise IrError(f"事件 {evt['id']} 的 publisher 缺少 module")
            pub.setdefault("context", "task")
        for sub in evt["subscribers"]:
            if "handler" not in sub and "task" not in sub:
                raise IrError(f"事件 {evt['id']} 的 subscriber 必须含 handler 或 task")
            sub.setdefault("handler", None)
            sub.setdefault("task", None)
            sub.setdefault("context", "lvgl" if sub["handler"] else "task_queue")

    # ---- View 接口缺省值 ----
    for page in ir["view_interfaces"]:
        if "page" not in page:
            raise IrError("view_interfaces 项必须包含 page")
        page["functions"] = _expect_list(page, "functions")
        for fn in page["functions"]:
            if "name" not in fn:
                raise IrError(f"页面 {page['page']} 的 function 缺少 name")
            fn.setdefault("args", "void")
            fn.setdefault("returns", "void")
            fn.setdefault("doc", "")

    # ---- 任务订阅者汇总（任务骨架生成用） ----
    tasks = {}
    for evt in ir["events"]:
        for sub in evt["subscribers"]:
            if sub.get("context") == "task_queue" and "task" in sub:
                tasks.setdefault(str(sub["task"]), []).append(evt)
    ir["tasks"] = [{"name": name, "events": evts} for name, evts in tasks.items()]

    return ir
