"""generate / diagram / USER CODE 保留 / CLI 行为的测试。

对照样例：tools/examples/wifi_module.yaml（WiFi 模块）。
"""

import os
import re

import pytest

from mvl_gen.cli import main
from mvl_gen.checks import run_checks
from mvl_gen.codegen import extract_user_blocks, generate
from mvl_gen.diagram import render_mermaid
from mvl_gen.ir import load_ir

EXAMPLE = os.path.join(os.path.dirname(__file__), "..", "examples",
                       "wifi_module.yaml")


@pytest.fixture(scope="module")
def ir():
    return load_ir(EXAMPLE)


@pytest.fixture(scope="module")
def generated(tmp_path_factory, ir):
    out = tmp_path_factory.mktemp("gen")
    issues = run_checks(ir)
    generate(ir, issues, str(out))
    return str(out)


def _read(out_dir, name):
    with open(os.path.join(out_dir, name), encoding="utf-8") as f:
        return f.read()


# ---- §9.1：样例 YAML 静态检查无错误 ----

def test_example_has_no_errors(ir):
    from mvl_gen.checks import has_errors
    assert not has_errors(run_checks(ir))


# ---- §9.2：生成物清单与骨架内容 ----

def test_generates_all_expected_files(generated):
    names = set(os.listdir(generated))
    assert {
        "mvl_events.h", "mvl_model.h", "mvl_model.c", "mvl_vm.h", "mvl_vm.c",
        "mvl_view_wifi.h", "mvl_view_wifi.c", "mvl_task_net_manage.c",
        "wiring_report.md",
    } <= names


def test_events_h_enum_and_segments(generated):
    text = _read(generated, "mvl_events.h")
    assert "EVT_WIFI_SCAN_UPDATED = 32" in text
    assert "EVT_WIFI_CONN_CHANGED = 33" in text
    assert "EVT_CMD_WIFI_CONNECT = 96" in text
    assert "_Static_assert(EVT_APP_MAX <= MVL_EVT_MAX_ID" in text


def test_model_h_state_struct(generated):
    text = _read(generated, "mvl_model.h")
    assert "mvl_wifi_ap_t wifi_aps[10];" in text
    assert "char wifi_pending_ssid[33];" in text
    assert "mvl_state_t mvl_model_snapshot(void);" in text
    assert "void mvl_model_set_wifi_conn_state(mvl_wifi_conn_state_t state);" in text


def test_model_c_setter_binds_publish(generated):
    text = _read(generated, "mvl_model.c")
    # set_xxx 骨架：互斥写（移植层 mutex）+ 发布对应事件（C5 由构造保证）
    assert "mvl_port_mutex_lock(s_lock);" in text
    assert "mvl_evt_publish(EVT_WIFI_SCAN_UPDATED, NULL);" in text
    assert "mvl_evt_publish(EVT_WIFI_CONN_CHANGED, NULL);" in text
    # 无事件的 setter 只写不发
    m = re.search(r"void mvl_model_set_pending_wifi_cred\(.*?\n\}", text, re.DOTALL)
    assert m and "mvl_evt_publish" not in m.group(0)


def test_vm_c_subscriptions_and_callbacks(generated):
    text = _read(generated, "mvl_vm.c")
    assert ("mvl_evt_subscribe(EVT_WIFI_SCAN_UPDATED, on_wifi_scan_updated,"
            " MVL_EVT_CTX_LVGL, NULL);") in text
    assert "static void on_wifi_conn_changed(const mvl_evt_t *evt)" in text
    assert "mvl_model_snapshot()" in text


def test_view_files(generated):
    header = _read(generated, "mvl_view_wifi.h")
    assert ("void mvl_view_wifi_show_scan_results(uint16_t count, "
            "const mvl_wifi_ap_t *aps, mvl_wifi_scan_state_t state);") in header
    assert "const char* mvl_view_wifi_get_selected_ssid(void);" in header
    src = _read(generated, "mvl_view_wifi.c")
    assert "USER CODE BEGIN wifi_show_scan_results" in src


def test_task_skeleton(generated):
    text = _read(generated, "mvl_task_net_manage.c")
    assert ("mvl_evt_subscribe(EVT_CMD_WIFI_CONNECT, NULL,"
            " MVL_EVT_CTX_TASK, s_net_manage_queue);") in text
    assert "case EVT_CMD_WIFI_CONNECT:" in text


def test_wiring_report(generated):
    text = _read(generated, "wiring_report.md")
    assert "发布/订阅矩阵" in text
    assert "EVT_CMD_WIFI_CONNECT" in text
    assert "静态检查结果" in text


# ---- USER CODE 段保留 ----

def test_user_code_preserved_on_regeneration(tmp_path, ir):
    out = str(tmp_path)
    generate(ir, [], out)

    vm_path = os.path.join(out, "mvl_vm.c")
    with open(vm_path, encoding="utf-8") as f:
        text = f.read()
    hand = ('\n    mvl_state_t s = mvl_model_snapshot();\n'
            '    mvl_view_wifi_show_conn_state(s.wifi_conn_state, '
            's.wifi_pending_ssid);\n    ')
    text = text.replace(
        re.search(r"/\* USER CODE BEGIN on_wifi_conn_changed \*/.*?"
                  r"/\* USER CODE END on_wifi_conn_changed \*/",
                  text, re.DOTALL).group(0),
        "/* USER CODE BEGIN on_wifi_conn_changed */" + hand +
        "/* USER CODE END on_wifi_conn_changed */")
    with open(vm_path, "w", encoding="utf-8") as f:
        f.write(text)

    generate(ir, [], out)  # 重新生成
    with open(vm_path, encoding="utf-8") as f:
        regen = f.read()
    assert hand in regen  # 手写内容保留
    assert "mvl_evt_subscribe(EVT_WIFI_CONN_CHANGED" in regen  # 骨架仍重生成


def test_extract_user_blocks():
    text = ("/* USER CODE BEGIN a */\nhello\n/* USER CODE END a */\n"
            "/* USER CODE BEGIN b */x/* USER CODE END b */")
    blocks = extract_user_blocks(text)
    assert blocks == {"a": "\nhello\n", "b": "x"}


# ---- §9.3：错误 YAML 时 CLI 非零退出 ----

def test_cli_check_fails_on_lvgl_to_lvgl(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("""\
project: t
events:
  - id: EVT_X
    segment: 32
    payload: none
    publishers:
      - { module: view_a, context: lvgl }
    subscribers:
      - { handler: on_x, context: lvgl }
""", encoding="utf-8")
    assert main(["check", str(bad)]) == 1
    assert main(["generate", str(bad), "-o", str(tmp_path / "out")]) == 1
    assert not (tmp_path / "out" / "mvl_events.h").exists()


def test_cli_check_passes_on_example():
    assert main(["check", EXAMPLE]) == 0


def test_cli_generate_example(tmp_path):
    out = tmp_path / "out"
    assert main(["generate", EXAMPLE, "-o", str(out)]) == 0
    assert (out / "mvl_events.h").exists()


def test_cli_missing_file_returns_2(capsys):
    assert main(["check", "/nonexistent.yaml"]) == 2


# ---- mermaid 导出 ----

def test_diagram_contains_wiring(ir):
    text = render_mermaid(ir)
    assert "flowchart LR" in text
    assert "EVT_WIFI_SCAN_UPDATED" in text
    assert "wifi_scan" in text
    assert "on_wifi_scan_updated" in text
    assert "net_manage" in text
    assert "mvl_model_set_wifi_conn_state" in text


def test_cli_diagram(tmp_path):
    out = tmp_path / "wiring.md"
    assert main(["diagram", EXAMPLE, "-o", str(out)]) == 0
    assert "```mermaid" in out.read_text(encoding="utf-8")
