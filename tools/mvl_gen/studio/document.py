"""studio/document.py —— mvl-studio 的数据模型层（无 GUI 依赖，可无头测试）。

职责：
  - 新建（从模板）/ 打开 / 保存 YAML；
  - 保存结果必须是能被 mvl_gen.ir 正常加载的合法 YAML；
  - 全量静态检查（复用 ir.load_ir_text + checks.run_checks）；
  - 把检查结果映射到树节点路径，供检查面板点击定位。

节点路径约定（元组，与 GUI 左树层级一致）：
  ("project",) ("config",) ("types",)
  ("model", i) ("setters", i)
  ("events", i) ("events", i, "publishers", j) ("events", i, "subscribers", j)
  ("view_interfaces", i) ("view_interfaces", i, "functions", j)
"""

import os
from collections import namedtuple

import yaml

from ..checks import has_errors, run_checks
from ..ir import IrError, load_ir_text

# 树节点路径 -> 展示名（检查面板「位置」列用）
_SECTION_LABELS = {
    "project": "项目",
    "config": "配置",
    "types": "契约类型",
    "model": "Model 字段",
    "setters": "写接口",
    "events": "事件",
    "view_interfaces": "View 接口",
    "publishers": "发布者",
    "subscribers": "订阅者",
    "functions": "函数",
}

# 检查面板行：rule/level/message 来自 checks.Issue，path 为定位用节点路径
IssueView = namedtuple("IssueView", ["rule", "level", "message", "path"])

_TEMPLATE_CANDIDATES = [
    # 源码树：tools/examples/mvl_project.template.yaml
    os.path.join(os.path.dirname(__file__), "..", "..", "examples",
                 "mvl_project.template.yaml"),
    # 兼容包内副本（wheel 安装场景）
    os.path.join(os.path.dirname(__file__), "mvl_project.template.yaml"),
]

# 模板文件都不可用时的兜底最小项目
_FALLBACK_DATA = {
    "project": "my_project",
    "mvl_version": "0.1.0",
    "config": {},
    "types": "",
    "model": [],
    "setters": [],
    "events": [],
    "view_interfaces": [],
}

_LIST_SECTIONS = ("model", "setters", "events", "view_interfaces")


class StudioDocument:
    """一份 mvl_project.yaml 的内存模型。data 为纯 dict/list/str 结构。"""

    def __init__(self, data=None, path=None):
        self.path = path
        self.data = self._normalize(data if data is not None else dict(_FALLBACK_DATA))
        self.dirty = False

    # ---- 构造 ----

    @classmethod
    def new_from_template(cls, template_path=None):
        """从注释模板新建项目（取其中的示例值占位）。"""
        candidates = [template_path] if template_path else []
        candidates += _TEMPLATE_CANDIDATES
        for cand in candidates:
            if cand and os.path.exists(cand):
                with open(cand, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if isinstance(data, dict):
                    return cls(data)
        return cls(dict(_FALLBACK_DATA))

    @classmethod
    def load(cls, path):
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise IrError("YAML 顶层必须是 mapping")
        return cls(data, path=path)

    @staticmethod
    def _normalize(data):
        """补齐各节缺省值，保证 GUI/生成器拿到稳定结构。"""
        out = dict(data)
        out.setdefault("project", "my_project")
        out.setdefault("mvl_version", "0.1.0")
        out["config"] = out.get("config") or {}
        out["types"] = out.get("types") or ""
        for section in _LIST_SECTIONS:
            value = out.get(section)
            out[section] = list(value) if isinstance(value, list) else []
        return out

    # ---- 序列化 ----

    def to_yaml(self):
        """序列化为合法 YAML 文本（注释不保留——GUI 保存后以结构为准）。"""
        data = dict(self.data)
        # 空节不写出，保持文件干净
        for key in ("config", "types") + _LIST_SECTIONS:
            if not data.get(key):
                data.pop(key, None)
        return yaml.safe_dump(data, allow_unicode=True, sort_keys=False,
                              default_flow_style=False)

    def save(self, path=None):
        path = path or self.path
        if not path:
            raise ValueError("未指定保存路径")
        text = self.to_yaml()
        load_ir_text(text)  # 保存前自检：写出的 YAML 必须能被 ir 加载
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        self.path = path
        self.dirty = False
        return path

    # ---- 检查 ----

    def validate(self):
        """全量静态检查，返回 IssueView 列表（含树节点路径）。

        YAML 结构错误（IrError）作为 rule='YAML' 的错误返回。
        """
        try:
            ir = load_ir_text(self.to_yaml())
        except (IrError, yaml.YAMLError) as e:
            return [IssueView("YAML", "错误", f"YAML 结构错误: {e}", ("project",))]
        issues = run_checks(ir)
        return [IssueView(i.rule, i.level, i.message, self._locate(i.message, ir))
                for i in issues]

    def has_errors(self):
        return any(i.level == "错误" for i in self.validate())

    # ---- 检查结论 -> 树节点定位 ----

    def _locate(self, message, ir):
        """按消息中出现的名字自细到粗匹配节点路径。"""
        # 事件 ID（含 setter 发布未定义事件里的事件名）
        for idx, evt in enumerate(ir.get("events", [])):
            if evt["id"] in message:
                for j, pub in enumerate(evt["publishers"]):
                    if pub["module"] in message:
                        return ("events", idx, "publishers", j)
                for j, sub in enumerate(evt["subscribers"]):
                    if (sub.get("handler") or sub.get("task") or "") in message:
                        return ("events", idx, "subscribers", j)
                return ("events", idx)
        # Model 字段
        for idx, field in enumerate(ir.get("model", [])):
            if field["name"] in message:
                return ("model", idx)
        # setter（消息里是全名 mvl_model_set_<name>）
        for idx, st in enumerate(self.data["setters"]):
            if f"mvl_model_set_{st.get('name', '')}" in message:
                return ("setters", idx)
        # View 接口
        for idx, page in enumerate(self.data["view_interfaces"]):
            for j, fn in enumerate(page.get("functions") or []):
                if fn.get("name") and f"接口 {fn['name']}" in message:
                    return ("view_interfaces", idx, "functions", j)
            if f"页面 {page.get('page', '')}" in message:
                return ("view_interfaces", idx)
        return ("project",)

    @staticmethod
    def format_path(path):
        """节点路径 -> 人读位置串，如 事件[2] / 发布者[0]。"""
        if not path:
            return ""
        parts = []
        idx = 0
        while idx < len(path):
            key = path[idx]
            label = _SECTION_LABELS.get(key, str(key))
            if idx + 1 < len(path) and isinstance(path[idx + 1], int):
                parts.append(f"{label}[{path[idx + 1]}]")
                idx += 2
            else:
                parts.append(label)
                idx += 1
        return " / ".join(parts)
