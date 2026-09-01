"""静态检查规则 C1/C2/C3/C4/C7/C8 的单元测试。"""

import pytest

from mvl_gen.checks import ERROR, WARNING, run_checks
from mvl_gen.ir import IrError, load_ir

BASE = """\
project: t
mvl_version: 0.1.0
model:
  - { name: counter, type: uint32_t }
events:
  - id: EVT_A
    segment: 32
    payload: none
    publishers:
      - { module: producer, context: task }
    subscribers:
      - { handler: on_a, context: lvgl }
"""


def _ir(tmp_path, text):
    p = tmp_path / "mvl_project.yaml"
    p.write_text(text, encoding="utf-8")
    return load_ir(str(p))


def _rules(issues, level=ERROR):
    return {i.rule for i in issues if i.level == level}


def test_base_yaml_passes_without_error(tmp_path):
    ir = _ir(tmp_path, BASE)
    assert ERROR not in {i.level for i in run_checks(ir)}


def test_c1_lvgl_to_lvgl_is_error(tmp_path):
    text = BASE.replace("module: producer, context: task",
                        "module: view_x, context: lvgl")
    issues = run_checks(_ir(tmp_path, text))
    assert "C1" in _rules(issues)


def test_c2_payload_over_8_bytes_is_error(tmp_path):
    text = BASE.replace("payload: none", 'payload: "uint8_t[16]"')
    issues = run_checks(_ir(tmp_path, text))
    assert "C2" in _rules(issues)


def test_c2_payload_within_8_bytes_ok(tmp_path):
    text = BASE.replace("payload: none", "payload: uint32_t")
    issues = run_checks(_ir(tmp_path, text))
    assert "C2" not in _rules(issues)


def test_c7_payload_pointer_is_error(tmp_path):
    text = BASE.replace("payload: none", 'payload: "const char *"')
    issues = run_checks(_ir(tmp_path, text))
    assert "C7" in _rules(issues)


def test_c3_isr_with_lvgl_subscriber_needs_pool(tmp_path):
    text = BASE.replace("context: task", "context: isr")
    issues = run_checks(_ir(tmp_path, text))
    assert "C3" in _rules(issues)

    text_with_pool = "config:\n  lvgl_job_pool: 8\n" + text
    issues = run_checks(_ir(tmp_path, text_with_pool))
    assert "C3" not in _rules(issues)


def test_c4_event_without_subscriber_is_warning(tmp_path):
    text = BASE + """\
  - id: EVT_ORPHAN
    segment: 64
    payload: none
    publishers:
      - { module: producer, context: task }
"""
    issues = run_checks(_ir(tmp_path, text))
    c4 = [i for i in issues if i.rule == "C4" and i.level == WARNING]
    assert any("EVT_ORPHAN" in i.message for i in c4)


def test_c8_duplicate_event_value_is_error(tmp_path):
    text = BASE + """\
  - id: EVT_B
    segment: 32
    value: 32
    payload: none
    publishers:
      - { module: producer, context: task }
    subscribers:
      - { handler: on_b, context: lvgl }
"""
    issues = run_checks(_ir(tmp_path, text))
    c8 = [i for i in issues if i.rule == "C8" and i.level == ERROR]
    assert any("撞号" in i.message for i in c8)


def test_c8_segment_overflow_is_error(tmp_path):
    # 段 32 的事件显式取 value=64，越过下一分段基址 64 → 越段
    text = BASE.replace("segment: 32", "segment: 32\n    value: 64") + """\
  - id: EVT_B
    segment: 64
    payload: none
    publishers:
      - { module: producer, context: task }
    subscribers:
      - { handler: on_b, context: lvgl }
"""
    issues = run_checks(_ir(tmp_path, text))
    c8 = [i for i in issues if i.rule == "C8" and i.level == ERROR]
    assert any("越段" in i.message for i in c8)


def test_c8_duplicate_view_signature_is_error(tmp_path):
    text = BASE + """\
view_interfaces:
  - page: wifi
    functions:
      - { name: show, args: "void" }
      - { name: show, args: "int x" }
"""
    issues = run_checks(_ir(tmp_path, text))
    c8 = [i for i in issues if i.rule == "C8" and i.level == ERROR]
    assert any("重复定义" in i.message for i in c8)


def test_ir_missing_project_is_structural_error(tmp_path):
    with pytest.raises(IrError):
        _ir(tmp_path, "events: []\n")
