"""studio/main_window.py —— mvl-studio 主窗口（PySide6）。

布局：左树（接线结构）/ 右上属性编辑（表单或表格）/ 底部检查面板。
所有编辑直接写回 StudioDocument.data，防抖 400ms 后全量重跑静态检查。
GUI 保持薄：YAML 往返、检查、定位逻辑都在 document.py。
"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPlainTextEdit, QPushButton, QSplitter, QStackedWidget,
    QTabWidget, QTableWidget, QTableWidgetItem, QToolBar, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from ..checks import run_checks
from ..codegen import generate
from ..ir import IrError, PUB_CONTEXTS, SUB_CONTEXTS, load_ir_text
from . import help_texts
from .diagram_view import DiagramView
from .document import StudioDocument

# 列表型节点的表格列定义：(键, 列名, 可选下拉值)
_TABLE_SCHEMAS = {
    "model": [("name", "字段名"), ("type", "类型"), ("doc", "说明")],
    "setters": [("name", "接口名(set_<name>)"), ("args", "参数"),
                ("event", "绑定事件(可空)"), ("doc", "说明")],
    "events": [("id", "事件 ID"), ("segment", "段基址"), ("value", "显式值(可空)"),
               ("payload", "载荷"), ("doc", "说明")],
    "publishers": [("module", "模块"), ("context", "上下文", PUB_CONTEXTS)],
    "subscribers": [("handler", "VM 回调(与任务二选一)"), ("task", "任务名"),
                    ("context", "上下文", SUB_CONTEXTS)],
    "functions": [("name", "函数名"), ("args", "参数"), ("returns", "返回类型"),
                  ("doc", "说明")],
    "view_interfaces": [("page", "页面名")],
}

_VALIDATE_DELAY_MS = 400


class MainWindow(QMainWindow):
    def __init__(self, document=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("mvl-studio —— MVL 接线设计编辑器")
        self.resize(1100, 720)

        self.doc = document or StudioDocument.new_from_template()
        self._loading = False  # 填充控件期间屏蔽写回

        self._build_ui()
        self.reload_tree()

        self._validate_timer = QTimer(self)
        self._validate_timer.setSingleShot(True)
        self._validate_timer.timeout.connect(self.run_checks_now)
        self.run_checks_now()
        self.show_welcome()

    # ================= UI 构建 =================

    def _build_ui(self):
        toolbar = QToolBar("主工具栏", self)
        self.addToolBar(toolbar)
        for text, slot in [("新建", self.on_new), ("打开...", self.on_open),
                           ("保存", self.on_save), ("另存为...", self.on_save_as),
                           ("生成代码...", self.on_generate)]:
            toolbar.addAction(text, slot)

        self.tree = QTreeWidget(self)
        self.tree.setHeaderLabel("接线结构")
        self.tree.currentItemChanged.connect(self.on_tree_select)

        # 右侧：各类节点的编辑器页
        self.stack = QStackedWidget(self)
        self._pages = {}
        self._add_project_page()
        self._add_config_page()
        self._add_types_page()
        for kind in _TABLE_SCHEMAS:
            self._add_table_page(kind)

        # 底部：检查面板
        self.issues = QTableWidget(0, 4, self)
        self.issues.setHorizontalHeaderLabels(["规则", "级别", "位置", "消息"])
        self.issues.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.Stretch)
        self.issues.setEditTriggers(QTableWidget.NoEditTriggers)
        self.issues.setSelectionBehavior(QTableWidget.SelectRows)
        self.issues.itemDoubleClicked.connect(self.on_issue_activated)
        self.issues.setMaximumHeight(180)

        # 右侧顶部：可折叠的分区说明框（内容随选中节点切换）
        self.info_box = QGroupBox("说明", self)
        self.info_box.setCheckable(True)
        self.info_box.setChecked(True)
        iv = QVBoxLayout(self.info_box)
        self.info_label = QLabel(self.info_box)
        self.info_label.setWordWrap(True)
        self.info_label.setTextFormat(Qt.RichText)
        iv.addWidget(self.info_label)

        # Tab：属性编辑 / 架构示意图
        self.diagram = DiagramView(self)
        self.tabs = QTabWidget(self)
        self.tabs.addTab(self.stack, "属性编辑")
        self.tabs.addTab(self.diagram, "架构示意图")
        self.tabs.currentChanged.connect(self._on_tab_changed)

        right = QWidget(self)
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.addWidget(self.info_box)
        rv.addWidget(self.tabs)
        rv.addWidget(QLabel("静态检查（双击定位到节点）："))
        rv.addWidget(self.issues)

        splitter = QSplitter(Qt.Horizontal, self)
        splitter.addWidget(self.tree)
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)

    def _add_project_page(self):
        w = QWidget(self)
        form = QFormLayout(w)
        self.edit_project = QLineEdit(w)
        self.edit_version = QLineEdit(w)
        form.addRow("项目名", self.edit_project)
        form.addRow("MVL 版本", self.edit_version)
        self.edit_project.editingFinished.connect(
            lambda: self._set_scalar("project", self.edit_project.text()))
        self.edit_version.editingFinished.connect(
            lambda: self._set_scalar("mvl_version", self.edit_version.text()))
        self._register_page("project", w)

    def _add_config_page(self):
        w = QWidget(self)
        form = QFormLayout(w)
        self.edit_pool = QLineEdit(w)
        self.edit_pool.setPlaceholderText("LVGL 投递池深度（整数，留空=不配置）")
        form.addRow("lvgl_job_pool", self.edit_pool)
        self.edit_pool.editingFinished.connect(self._on_pool_changed)
        self._register_page("config", w)

    def _add_types_page(self):
        w = QWidget(self)
        v = QVBoxLayout(w)
        v.addWidget(QLabel("契约类型（原始 C 片段，进入 mvl_model.h 的 USER CODE 段）："))
        self.edit_types = QPlainTextEdit(w)
        v.addWidget(self.edit_types)
        self.edit_types.textChanged.connect(
            lambda: self._set_scalar("types", self.edit_types.toPlainText()))
        self._register_page("types", w)

    def _add_table_page(self, kind):
        w = QWidget(self)
        v = QVBoxLayout(w)
        table = QTableWidget(0, len(_TABLE_SCHEMAS[kind]), w)
        table.setHorizontalHeaderLabels([c[1] for c in _TABLE_SCHEMAS[kind]])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.itemChanged.connect(lambda item, k=kind: self._on_cell(k, item))
        btns = QHBoxLayout()
        add = QPushButton("添加行", w)
        remove = QPushButton("删除选中行", w)
        add.clicked.connect(lambda _=False, k=kind: self._add_row(k))
        remove.clicked.connect(lambda _=False, k=kind: self._remove_row(k))
        btns.addWidget(add)
        btns.addWidget(remove)
        btns.addStretch(1)
        v.addWidget(table)
        v.addLayout(btns)
        self._register_page(kind, w, table=table)

    def _register_page(self, kind, widget, table=None):
        self._pages[kind] = (widget, table)
        self.stack.addWidget(widget)

    # ================= 左树 =================

    def reload_tree(self):
        """按 document.data 全量重建左树（结构变更后调用）。"""
        self._loading = True
        self.tree.clear()
        d = self.doc.data

        def item(text, path, parent):
            it = QTreeWidgetItem(parent, [text])
            it.setData(0, Qt.UserRole, tuple(path))
            kind, _ = self._node_kind(path)
            if kind in help_texts.TOOLTIPS:
                it.setToolTip(0, help_texts.TOOLTIPS[kind])
            return it

        item(f"项目: {d.get('project', '')}", ("project",), self.tree)
        item("配置 config", ("config",), self.tree)
        item("契约类型 types", ("types",), self.tree)

        model = item("Model 字段", ("model",), self.tree)
        for i, f in enumerate(d["model"]):
            item(f.get("name", "?"), ("model", i), model)

        setters = item("写接口 setters", ("setters",), self.tree)
        for i, s in enumerate(d["setters"]):
            item(f"set_{s.get('name', '?')}", ("setters", i), setters)

        events = item("事件 events", ("events",), self.tree)
        for i, e in enumerate(d["events"]):
            ev = item(e.get("id", "?"), ("events", i), events)
            pubs = item("发布者", ("events", i, "publishers"), ev)
            for j, p in enumerate(e.get("publishers") or []):
                item(f"{p.get('module', '?')}({p.get('context', '')})",
                     ("events", i, "publishers", j), pubs)
            subs = item("订阅者", ("events", i, "subscribers"), ev)
            for j, s in enumerate(e.get("subscribers") or []):
                name = s.get("handler") or s.get("task") or "?"
                item(f"{name}({s.get('context', '')})",
                     ("events", i, "subscribers", j), subs)

        views = item("View 接口", ("view_interfaces",), self.tree)
        for i, p in enumerate(d["view_interfaces"]):
            pg = item(p.get("page", "?"), ("view_interfaces", i), views)
            for j, fn in enumerate(p.get("functions") or []):
                item(fn.get("name", "?"),
                     ("view_interfaces", i, "functions", j), pg)

        self.tree.expandAll()
        self._loading = False

    def on_tree_select(self, current, _previous):
        if current is None:
            return
        path = current.data(0, Qt.UserRole)
        self.show_node(path)

    def show_node(self, path):
        """按节点路径在右侧显示对应编辑器，并同步控件内容与说明框。"""
        kind, row = self._node_kind(path)
        self.set_info(kind)
        widget, table = self._pages[kind]
        self.stack.setCurrentWidget(widget)
        self._loading = True
        try:
            if kind == "project":
                self.edit_project.setText(str(self.doc.data.get("project", "")))
                self.edit_version.setText(
                    str(self.doc.data.get("mvl_version", "")))
            elif kind == "config":
                pool = self.doc.data["config"].get("lvgl_job_pool")
                self.edit_pool.setText("" if pool is None else str(pool))
            elif kind == "types":
                self.edit_types.setPlainText(self.doc.data.get("types", ""))
            else:
                self._fill_table(kind, self._rows_for(path, kind))
                if row is not None and row < table.rowCount():
                    table.selectRow(row)
        finally:
            self._loading = False

    def set_info(self, kind):
        """切换说明框内容到指定节点类别。"""
        title, body = help_texts.NODE_HELP.get(kind, ("说明", ""))
        self.info_box.setTitle(f"说明：{title}")
        self.info_label.setText(body)

    def show_welcome(self):
        """新建/启动时的「五步上手」提示。"""
        self.info_box.setTitle("说明：快速上手")
        self.info_label.setText(help_texts.WELCOME)
        self.statusBar().showMessage(
            "五步上手：类型 → 状态字段 → 写接口绑事件 → 事件接线 → View 接口 → 生成代码",
            10000)

    @staticmethod
    def _node_kind(path):
        """节点路径 -> (编辑器页 kind, 需高亮的行)。"""
        if path[0] in ("project", "config", "types"):
            return path[0], None
        if path[0] in ("model", "setters"):
            row = path[1] if len(path) > 1 else None
            return path[0], row
        if path[0] == "view_interfaces":
            # 页面节点 / 函数节点 → 该页面的函数表；节根 → 页面列表
            if len(path) >= 2:
                row = path[3] if len(path) > 3 else None
                return "functions", row
            return "view_interfaces", None
        if path[0] == "events":
            if len(path) >= 3 and path[2] in ("publishers", "subscribers"):
                row = path[3] if len(path) > 3 else None
                return path[2], row
            row = path[1] if len(path) > 1 else None
            return "events", row
        return "project", None

    def _rows_for(self, path, kind):
        """取该表格页当前应编辑的行列表（挂到文档数据上）。"""
        d = self.doc.data
        if kind in ("model", "setters", "events", "view_interfaces"):
            return d[kind]
        if kind in ("publishers", "subscribers"):
            evt = d["events"][path[1]]
            return evt.setdefault(kind, [])
        if kind == "functions":
            page = d["view_interfaces"][path[1]]
            return page.setdefault("functions", [])
        return []

    # ================= 表格编辑 =================

    def _fill_table(self, kind, rows):
        _, table = self._pages[kind]
        schema = _TABLE_SCHEMAS[kind]
        self._loading = True
        try:
            table.setRowCount(len(rows))
            for r, row in enumerate(rows):
                for c, col in enumerate(schema):
                    key = col[0]
                    choices = col[2] if len(col) > 2 else None
                    value = row.get(key)
                    if choices:
                        combo = QComboBox(table)
                        combo.addItems(choices)
                        combo.setEditable(False)
                        combo.setCurrentText(str(value) if value else choices[0])
                        combo.currentTextChanged.connect(
                            lambda text, k=kind, rr=r, kk=key:
                            self._on_combo(k, rr, kk, text))
                        table.setCellWidget(r, c, combo)
                    else:
                        text = "" if value is None else str(value)
                        table.setItem(r, c, QTableWidgetItem(text))
        finally:
            self._loading = False

    def _current_rows(self, kind):
        """表格页当前绑定的数据行（由当前树节点决定）。"""
        current = self.tree.currentItem()
        if current is None:
            return None
        path = current.data(0, Qt.UserRole)
        node_kind, _ = self._node_kind(path)
        if node_kind != kind:
            return None
        return self._rows_for(path, kind)

    def _on_cell(self, kind, item):
        if self._loading:
            return
        rows = self._current_rows(kind)
        if rows is None or item.row() >= len(rows):
            return
        key = _TABLE_SCHEMAS[kind][item.column()][0]
        text = item.text().strip()
        if key in ("segment", "value", "lvgl_job_pool"):
            rows[item.row()][key] = int(text) if text.lstrip("-").isdigit() else None
            if key == "value" and not text:
                rows[item.row()].pop("value", None)  # 留空 = 自动编号
        else:
            rows[item.row()][key] = text
        self._after_edit(structure=(key in ("id", "name", "page", "module",
                                            "handler", "task")))

    def _on_combo(self, kind, row, key, text):
        if self._loading:
            return
        rows = self._current_rows(kind)
        if rows is None or row >= len(rows):
            return
        rows[row][key] = text
        self._after_edit(structure=True)

    def _add_row(self, kind):
        rows = self._current_rows(kind)
        if rows is None:
            return
        defaults = {
            "model": {"name": "new_field", "type": "uint32_t"},
            "setters": {"name": "new_setter", "args": "void"},
            "events": {"id": "EVT_NEW", "segment": 32, "payload": "none",
                       "publishers": [], "subscribers": []},
            "publishers": {"module": "new_module", "context": "task"},
            "subscribers": {"handler": "on_new", "context": "lvgl"},
            "functions": {"name": "new_fn", "args": "void"},
            "view_interfaces": {"page": "new_page", "functions": []},
        }
        rows.append(dict(defaults[kind]))
        self._after_edit(structure=True)

    def _remove_row(self, kind):
        rows = self._current_rows(kind)
        _, table = self._pages[kind]
        row = table.currentRow()
        if rows is None or row < 0 or row >= len(rows):
            return
        del rows[row]
        self._after_edit(structure=True)

    # ================= 表单写回 =================

    def _set_scalar(self, key, value):
        if self._loading:
            return
        self.doc.data[key] = value
        self._after_edit(structure=(key == "project"))

    def _on_pool_changed(self):
        if self._loading:
            return
        text = self.edit_pool.text().strip()
        if text.isdigit():
            self.doc.data["config"]["lvgl_job_pool"] = int(text)
        else:
            self.doc.data["config"].pop("lvgl_job_pool", None)
        self._after_edit(structure=False)

    def _after_edit(self, structure):
        """编辑后统一收口：标脏、必要时重建树、防抖重跑检查。"""
        self.doc.dirty = True
        if structure:
            self.reload_tree()
        self._validate_timer.start(_VALIDATE_DELAY_MS)

    def _on_tab_changed(self, index):
        if self.tabs.widget(index) is self.diagram:
            self.diagram.refresh(self.doc.data)

    # ================= 检查面板 =================

    def run_checks_now(self):
        views = self.doc.validate()
        self.diagram.refresh(self.doc.data)  # 示意图随文档（防抖后）重绘
        self.issues.setRowCount(len(views))
        for r, iv in enumerate(views):
            cells = [iv.rule, iv.level, StudioDocument.format_path(iv.path),
                     iv.message]
            for c, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if iv.level == "错误":
                    item.setForeground(Qt.red)
                else:
                    item.setForeground(Qt.darkYellow)
                self.issues.setItem(r, c, item)
            self.issues.item(r, 0).setData(Qt.UserRole, iv.path)
        return views

    def on_issue_activated(self, item):
        row = item.row()
        path_item = self.issues.item(row, 0)
        path = path_item.data(Qt.UserRole) if path_item else None
        if path:
            self.select_tree_path(path)

    def select_tree_path(self, path):
        """按节点路径选中左树节点（找不到精确节点时退到最近的祖先）。"""
        for depth in range(len(path), 0, -1):
            target = tuple(path[:depth])
            found = self._find_tree_item(target)
            if found is not None:
                self.tree.setCurrentItem(found)
                self.tree.scrollToItem(found)
                return

    def _find_tree_item(self, path):
        stack = [self.tree.invisibleRootItem()]
        while stack:
            node = stack.pop()
            count = (node.childCount() if node is not self.tree.invisibleRootItem()
                     else self.tree.topLevelItemCount())
            for i in range(count):
                child = (node.child(i) if node is not self.tree.invisibleRootItem()
                         else self.tree.topLevelItem(i))
                if tuple(child.data(0, Qt.UserRole)) == path:
                    return child
                stack.append(child)
        return None

    # ================= 工具栏动作 =================

    def on_new(self):
        self.doc = StudioDocument.new_from_template()
        self.reload_tree()
        self.run_checks_now()
        self.show_welcome()

    def on_open(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "打开 mvl_project.yaml", "", "YAML (*.yaml *.yml)")
        if not path:
            return
        try:
            self.doc = StudioDocument.load(path)
        except (IrError, OSError) as e:
            QMessageBox.critical(self, "打开失败", str(e))
            return
        self.reload_tree()
        self.run_checks_now()

    def on_save(self):
        if not self.doc.path:
            return self.on_save_as()
        self._do_save(self.doc.path)

    def on_save_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "保存 mvl_project.yaml", "mvl_project.yaml", "YAML (*.yaml)")
        if not path:
            return
        self._do_save(path)

    def _do_save(self, path):
        views = self.run_checks_now()
        if any(iv.level == "错误" for iv in views):
            QMessageBox.warning(
                self, "存在检查错误",
                "静态检查发现错误，文件仍会保存；请修正后再生成代码。")
        try:
            self.doc.save(path)
        except (IrError, ValueError, OSError) as e:
            QMessageBox.critical(self, "保存失败", str(e))
            return
        self.setWindowTitle(f"mvl-studio —— {path}")

    def on_generate(self):
        views = self.run_checks_now()
        if any(iv.level == "错误" for iv in views):
            ret = QMessageBox.question(
                self, "存在检查错误", "静态检查发现错误，仍要生成代码吗？")
            if ret != QMessageBox.Yes:
                return
        out_dir = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if not out_dir:
            return
        try:
            ir = load_ir_text(self.doc.to_yaml())
            issues = run_checks(ir)
            written = generate(ir, issues, out_dir)
        except Exception as e:
            QMessageBox.critical(self, "生成失败", str(e))
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("生成完成")
        v = QVBoxLayout(dlg)
        v.addWidget(QLabel("生成文件：\n" + "\n".join(written)))
        buttons = QDialogButtonBox(QDialogButtonBox.Ok, dlg)
        buttons.accepted.connect(dlg.accept)
        v.addWidget(buttons)
        dlg.exec_()
