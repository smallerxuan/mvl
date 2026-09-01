"""diagram.py —— 从 IR 导出 mermaid 接线图。

输出一个包含 mermaid 代码块的 Markdown 文件：模块 → 事件 → 订阅者，
连线上标注执行上下文；Model 写接口与 View 接口作为旁注节点。
"""


def _node_id(text):
    """mermaid 节点 ID 只取安全字符。"""
    return "".join(c if c.isalnum() or c == "_" else "_" for c in text)


def render_mermaid(ir):
    """渲染 mermaid flowchart 文本。"""
    lines = ["flowchart LR"]
    lines.append(f"    subgraph MODEL[Model 状态中心 mvl_state_t]")
    for field in ir["model"]:
        lines.append(f"        F_{_node_id(field['name'])}[\"{field['name']}\"]")
    lines.append("    end")
    lines.append("")

    for evt in ir["events"]:
        evt_node = f"E_{_node_id(evt['id'])}"
        payload = evt.get("payload") or "none"
        label = f"{evt['id']} = {evt['value']}"
        lines.append(f"    {evt_node}(\"{label}<br/>payload: {payload}\")")
        for pub in evt["publishers"]:
            mod = f"P_{_node_id(pub['module'])}"
            pub_api = "mvl_evt_publish_isr" if pub["context"] == "isr" else "mvl_evt_publish"
            lines.append(f"    {mod}[\"{pub['module']}\"]")
            lines.append(f"    {mod} -- \"{pub_api}<br/>ctx: {pub['context']}\" --> {evt_node}")
        for sub in evt["subscribers"]:
            target = sub.get("handler") or sub.get("task")
            sub_node = f"S_{_node_id(str(target))}"
            if sub["context"] == "lvgl":
                lines.append(f"    {sub_node}[\"ViewModel {target}\"]")
                lines.append(f"    {evt_node} -- \"mvl_msg 投递<br/>ctx: lvgl\" --> {sub_node}")
            else:
                lines.append(f"    {sub_node}[\"任务 {target} 队列\"]")
                lines.append(f"    {evt_node} -- \"队列投递<br/>ctx: task_queue\" --> {sub_node}")
        lines.append("")

    for st in ir["setters"]:
        if st.get("event"):
            lines.append(f"    SET_{_node_id(st['name'])}[\"mvl_model_set_{st['name']}\"]")
            lines.append(f"    SET_{_node_id(st['name'])} -- \"写状态 + 发布\" --> E_{_node_id(st['event'])}")
    lines.append("")

    for page in ir["view_interfaces"]:
        lines.append(f"    subgraph VIEW_{_node_id(page['page'])}[View mvl_view_{page['page']}]")
        for fn in page["functions"]:
            lines.append(f"        V_{_node_id(page['page'])}_{_node_id(fn['name'])}[\"{fn['name']}()\"]")
        lines.append("    end")

    return "\n".join(lines) + "\n"


def export_diagram(ir, out_path):
    """写出包含 mermaid 代码块的 Markdown 文件。"""
    body = render_mermaid(ir)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"# {ir['project']} MVL 接线图\n\n"
                f"> 由 mvl-gen 从 mvl_project.yaml 自动生成。\n\n"
                f"```mermaid\n{body}```\n")
    return out_path
