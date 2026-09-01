"""mvl-studio 测试：数据层 round-trip（无头）+ GUI offscreen 冒烟。"""

import os

import pytest

from mvl_gen.ir import load_ir, load_ir_text
from mvl_gen.studio.document import StudioDocument

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

EXAMPLE = os.path.join(os.path.dirname(__file__), "..", "examples",
                       "wifi_module.yaml")
TEMPLATE = os.path.join(os.path.dirname(__file__), "..", "examples",
                        "mvl_project.template.yaml")


# ---------- 数据层（无头） ----------

def test_template_loads_and_passes_checks():
    doc = StudioDocument.new_from_template(TEMPLATE)
    errors = [iv for iv in doc.validate() if iv.level == "错误"]
    assert errors == []


def test_round_trip_new_edit_save_reload(tmp_path):
    doc = StudioDocument.new_from_template(TEMPLATE)
    # 改字段
    doc.data["project"] = "roundtrip"
    doc.data["model"].append({"name": "vol", "type": "uint8_t", "doc": "音量"})
    doc.data["events"][0]["subscribers"].append(
        {"task": "audio", "context": "task_queue"})
    out = tmp_path / "mvl_project.yaml"
    doc.save(str(out))

    # 保存结果必须能被 ir 正常加载
    ir = load_ir(str(out))
    assert ir["project"] == "roundtrip"
    assert any(t["name"] == "audio" for t in ir["tasks"])

    # 重新加载后数据一致
    doc2 = StudioDocument.load(str(out))
    assert doc2.data == StudioDocument.load(str(out)).data
    assert doc2.data["model"][-1]["name"] == "vol"
    assert doc2.data["events"][0]["subscribers"][-1]["task"] == "audio"


def test_save_rejects_structurally_invalid(tmp_path):
    doc = StudioDocument.new_from_template(TEMPLATE)
    doc.data["model"] = "not_a_list"  # 绕过 normalize 直接破坏结构
    with pytest.raises(Exception):
        doc.save(str(tmp_path / "bad.yaml"))


def test_validate_reports_constructed_errors_with_paths():
    doc = StudioDocument.new_from_template(TEMPLATE)
    # 构造 C1：发布者改成 lvgl，订阅者仍是 lvgl
    doc.data["events"][0]["publishers"][0]["context"] = "lvgl"
    views = doc.validate()
    c1 = [iv for iv in views if iv.rule == "C1"]
    assert c1 and c1[0].level == "错误"
    # 定位到事件下的发布者节点
    assert c1[0].path[0] == "events"
    assert "publishers" in c1[0].path
    assert "发布者" in StudioDocument.format_path(c1[0].path)


def test_validate_reports_payload_pointer_error():
    doc = StudioDocument.new_from_template(TEMPLATE)
    doc.data["events"][0]["payload"] = "const char *"
    rules = {iv.rule for iv in doc.validate() if iv.level == "错误"}
    assert "C7" in rules


def test_load_example_and_validate():
    doc = StudioDocument.load(EXAMPLE)
    errors = [iv for iv in doc.validate() if iv.level == "错误"]
    assert errors == []


def test_to_yaml_empty_sections_omitted():
    doc = StudioDocument({"project": "x"})
    text = doc.to_yaml()
    assert "events" not in text
    load_ir_text(text)  # 仍可加载


# ---------- GUI offscreen 冒烟 ----------

pyside6 = pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from mvl_gen.studio.main_window import MainWindow  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _make_window(qapp, tmp_path, doc=None):
    win = MainWindow(doc or StudioDocument.new_from_template(TEMPLATE))
    return win


def test_gui_new_from_template_populates_tree(qapp, tmp_path):
    win = _make_window(qapp, tmp_path)
    top = [win.tree.topLevelItem(i).text(0) for i in range(win.tree.topLevelItemCount())]
    assert any("项目" in t for t in top)
    assert any("事件" in t for t in top)
    win.close()


def test_gui_edit_field_save_reload(qapp, tmp_path):
    win = _make_window(qapp, tmp_path)
    # 通过项目表单改项目名
    win.show_node(("project",))
    win.edit_project.setText("gui_project")
    win.edit_project.editingFinished.emit()
    assert win.doc.data["project"] == "gui_project"

    out = tmp_path / "gui.yaml"
    win.doc.save(str(out))  # 直接走数据层保存（避开文件对话框）
    doc2 = StudioDocument.load(str(out))
    assert doc2.data["project"] == "gui_project"
    win.close()


def test_gui_table_add_row_and_edit(qapp, tmp_path):
    win = _make_window(qapp, tmp_path)
    before = len(win.doc.data["events"])
    win.select_tree_path(("events",))  # 选中「事件」节点，右侧出现事件表格
    win._add_row("events")
    assert len(win.doc.data["events"]) == before + 1
    assert win.doc.data["events"][-1]["id"] == "EVT_NEW"

    # 表格单元格编辑写回数据（重新选中，reload_tree 后行号不变）
    win.select_tree_path(("events",))
    table = win._pages["events"][1]
    item = table.item(before, 0)
    item.setText("EVT_EDITED")
    assert win.doc.data["events"][before]["id"] == "EVT_EDITED"
    win.close()


def _scene_texts(scene):
    """收集 QGraphicsScene 中全部文本项内容。"""
    out = []
    for it in scene.items():
        if hasattr(it, "toPlainText"):
            out.append(it.toPlainText())
    return "\n".join(out)


def test_gui_diagram_shows_wiring_texts(qapp, tmp_path):
    win = MainWindow(StudioDocument.load(EXAMPLE))
    win.tabs.setCurrentWidget(win.diagram)  # 切到架构示意图 tab 触发刷新
    texts = _scene_texts(win.diagram.scene)
    for expected in ["EVT_WIFI_SCAN_UPDATED", "EVT_CMD_WIFI_CONNECT",
                     "wifi_scan", "on_wifi_scan_updated", "页面 wifi",
                     "mvl_state_t 状态中心", "net_manage", "view_wifi_pass",
                     "UI 事件源 ctx: lvgl", "唯一允许调 lv_* 的地方"]:
        assert expected in texts, expected
    # 列标题
    for lane in ["后台任务", "事件总线", "ViewModel", "View / LVGL 主任务"]:
        assert lane in texts, lane
    # 发布者按上下文分列：后台发布者在第 1 列，lvgl 发布者在第 4 列
    boxes = win.diagram._boxes
    assert boxes[("pub", "wifi_scan")][0] == 0
    assert boxes[("pub", "net_manage")][0] == 0
    assert boxes[("uipub", "view_wifi_pass")][0] == 3
    win.close()


def test_gui_diagram_placeholder_on_empty_doc(qapp, tmp_path):
    win = MainWindow(StudioDocument({"project": "empty"}))
    win.diagram.refresh(win.doc.data)
    texts = _scene_texts(win.diagram.scene)
    assert "你定义的事件会出现在这里" in texts
    win.close()


def test_gui_info_box_follows_node_selection(qapp, tmp_path):
    win = _make_window(qapp, tmp_path)
    # 启动后为欢迎文案
    assert "五步上手" in win.info_label.text()

    win.show_node(("types",))
    assert "契约类型" in win.info_box.title()
    assert "mvl_model.h" in win.info_label.text()

    win.show_node(("events", 0, "subscribers"))
    assert "订阅者" in win.info_box.title()
    assert "二选一" in win.info_label.text()

    win.show_node(("view_interfaces", 0))
    assert "函数" in win.info_box.title()
    win.close()


def test_gui_issues_panel_shows_constructed_error(qapp, tmp_path):
    win = _make_window(qapp, tmp_path)
    win.doc.data["events"][0]["publishers"][0]["context"] = "lvgl"
    views = win.run_checks_now()
    assert any(iv.rule == "C1" for iv in views)
    assert win.issues.rowCount() == len(views)
    texts = [win.issues.item(r, 3).text() for r in range(win.issues.rowCount())]
    assert any("自我死锁" in t for t in texts)

    # 双击检查行可定位到树节点
    win.on_issue_activated(win.issues.item(0, 0))
    current = win.tree.currentItem()
    assert current is not None
    win.close()
