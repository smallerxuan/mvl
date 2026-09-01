"""codegen.py —— Jinja2 模板渲染 + USER CODE 段保留（CubeMX 惯例）。

重新生成时，已有文件中
    /* USER CODE BEGIN xxx */
    ...手写内容...
    /* USER CODE END xxx */
之间的内容原样保留，骨架部分全量重生成。
"""

import os
import re

from jinja2 import Environment, PackageLoader, StrictUndefined

USER_BLOCK_RE = re.compile(
    r"/\* USER CODE BEGIN (?P<name>[\w.\-]+) \*/(?P<body>.*?)"
    r"/\* USER CODE END (?P=name) \*/",
    re.DOTALL,
)

# 生成物清单：模板名 -> 输出文件名（相对 -o 目录，{page}/{task} 为占位）
_GENERATED_FILES = [
    ("mvl_events.h.j2", "mvl_events.h"),
    ("mvl_model.h.j2", "mvl_model.h"),
    ("mvl_model.c.j2", "mvl_model.c"),
    ("mvl_vm.h.j2", "mvl_vm.h"),
    ("mvl_vm.c.j2", "mvl_vm.c"),
]


def extract_user_blocks(text):
    """从已有文件文本中提取 USER CODE 段，返回 {name: body}。"""
    return {m.group("name"): m.group("body") for m in USER_BLOCK_RE.finditer(text)}


def _make_env(user_blocks):
    env = Environment(
        loader=PackageLoader("mvl_gen", "templates"),
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
        undefined=StrictUndefined,
    )

    def user_code(name, default=""):
        """模板内调用：返回已保留的手写内容，首次生成时用 default。"""
        return user_blocks.get(name, default)

    env.globals["user_code"] = user_code
    return env


def _render_file(env, template_name, context):
    return env.get_template(template_name).render(**context)


def generate(ir, issues, out_dir, report=True):
    """生成全部目标文件，返回写出的文件路径列表。

    issues 为静态检查结果（写入 wiring_report.md）。
    """
    os.makedirs(out_dir, exist_ok=True)
    written = []

    base_context = {"ir": ir, "project": ir["project"]}

    def render_to(template_name, filename, extra=None):
        path = os.path.join(out_dir, filename)
        user_blocks = {}
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                user_blocks = extract_user_blocks(f.read())
        env = _make_env(user_blocks)
        context = dict(base_context)
        if extra:
            context.update(extra)
        text = _render_file(env, template_name, context)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        written.append(path)

    for template_name, filename in _GENERATED_FILES:
        render_to(template_name, filename)

    for page in ir["view_interfaces"]:
        ctx = {"page": page}
        render_to("mvl_view.h.j2", f"mvl_view_{page['page']}.h", ctx)
        render_to("mvl_view.c.j2", f"mvl_view_{page['page']}.c", ctx)

    for task in ir["tasks"]:
        render_to("mvl_task.c.j2", f"mvl_task_{task['name']}.c", {"task": task})

    if report:
        render_to("wiring_report.md.j2", "wiring_report.md", {"issues": issues})

    return written
