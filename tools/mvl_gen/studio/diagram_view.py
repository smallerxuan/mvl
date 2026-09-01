"""studio/diagram_view.py —— 架构示意图视图（纯 PySide6 QGraphicsView 自绘）。

布局（用户拍板版）：

    ┌──────────────── Model（独占整行，宽=下方四列总宽）────────────────┐
    └──────────────────────┬───────────────────────────────────────────┘
                           │ 垂直落线「写状态后发事件」（底缘分散出点）
    ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────────────┐
    │ 后台任务  │──►│ 事件总线  │──►│ ViewModel │──►│ View/LVGL 主任务  │
    │ (发布者/  │发布 │ (事件框)  │LVGL投递│ (回调框)  │调用接口│ (页面框 +      │
    │  队列订阅) │◄──│          │◄─│          │   │  UI 事件源框)   │
    └──────────┘入队 └──────────┘发布└──────────┘   │  (ctx=lvgl 发布者)│
                                                    └──────────────────┘

布线：全部走列间隙/Model 下方走线带，不穿任何框。
  - 正向边（发布者→事件→回调→页面）：出右缘 → 间隙内折线 → 入左缘；
  - 回边（事件→队列订阅者）：出左缘 → 间隙（与正向线错开 x/y）→ 入右缘；
  - Model→事件：底缘分散出点垂直落到走线带 → 横向到列间隙 → 入事件框左缘
    （列内框体纵向堆叠，垂直直插顶缘必穿上方框，故改从间隙进左缘）。
标签：水平段上方、浅色不透明底；避让范围 = 框体 + 列标题带 + 已放置标签，
      逐级上挪，多次冲突则省略。
"""

import math

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush, QColor, QFont, QFontMetrics, QPainterPath, QPen, QPolygonF,
)
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView, QVBoxLayout, QWidget

# 下方四列定义：(标题, 底色, 空列占位提示)
COLS = [
    ("后台任务", "#eaf3ff", "发布者模块 / 订阅任务会出现在这里"),
    ("事件总线", "#fff8e0", "你定义的事件会出现在这里"),
    ("ViewModel", "#f5ecff", "LVGL 订阅回调（handler）会出现在这里"),
    ("View / LVGL 主任务", "#ffecec", "View 页面与接口函数会出现在这里"),
]

_COL_MIN_W = 220
_COL_GAP = 56
_MARGIN = 16
_HEADER_H = 34          # 列标题带高度（标签避让区）
_BOX_PAD = 12           # 框内边距（框宽 = 最长文本 + 2×_BOX_PAD）
_TEXT_MAX_W = 400       # 单行文本像素上限，超出截断加省略号
_TITLE_GAP = 4          # 框内标题与首行明细的垂直间距
_BOX_GAP = 18
_LABEL_BG = "#fffbe6"   # 箭头标签底色（不透明，防压线）
_STRIP_STEP = 9         # Model 下方走线带每条线的纵向间距
_STRIP_TOP = 10         # Model 底缘到走线带第一条线的距离


class DiagramView(QWidget):
    """架构示意图：QGraphicsView + 全量重绘的 QGraphicsScene。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.view = QGraphicsView(self)
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        layout.addWidget(self.view)
        self.scene = QGraphicsScene(self)
        self.view.setScene(self.scene)
        self._boxes = {}          # 节点键 -> (col, QRectF)；Model 为 ("model",)
        self._col_w = [_COL_MIN_W] * len(COLS)
        self._header_rects = []   # 列标题带（标签避让障碍）
        self._label_rects = []    # 已放置标签（标签避让障碍）

    # ================= 数据 -> 内容模型 =================

    def _collect(self, data):
        """返回 (model_lines, {col: [(key, 标题, 明细行), ...]})。"""
        content = {i: [] for i in range(len(COLS))}

        # 第 1 列：后台发布者模块（task/sys_evt/isr，按模块名去重汇总上下文）
        #         + 任务队列订阅者；ctx=lvgl 的发布者归第 4 列（UI 事件源）
        modules = {}
        ui_modules = {}
        tasks = {}
        for evt in data["events"]:
            for pub in evt.get("publishers") or []:
                if pub.get("context") == "lvgl":
                    ui_modules.setdefault(pub.get("module", "?"), set())
                else:
                    modules.setdefault(pub.get("module", "?"), set()).add(
                        pub.get("context", ""))
            for sub in evt.get("subscribers") or []:
                if sub.get("task"):
                    tasks.setdefault(sub["task"], set())
        for name, ctxs in modules.items():
            content[0].append((("pub", name), name,
                               ["发布者 ctx: " + ", ".join(sorted(c for c in ctxs if c))]))
        for name in tasks:
            content[0].append((("task", name), name, ["任务事件队列"]))

        # 第 2 列：事件
        for evt in data["events"]:
            content[1].append((("event", evt.get("id", "?")), evt.get("id", "?"),
                               [f"段 {evt.get('segment', '?')}",
                                f"载荷 {evt.get('payload') or 'none'}"]))

        # 第 3 列：LVGL 订阅回调
        for evt in data["events"]:
            for sub in evt.get("subscribers") or []:
                if sub.get("handler"):
                    content[2].append((("handler", sub["handler"]), sub["handler"],
                                       [f"订阅 {evt.get('id', '?')}",
                                        "ctx: lvgl（可操作 UI）"]))

        # 第 4 列：View 页面 + UI 事件源（ctx=lvgl 的发布者，画在页面框下方）
        for page in data["view_interfaces"]:
            name = page.get("page", "?")
            lines = [f"{fn.get('name', '?')}()"
                     for fn in page.get("functions") or []]
            lines.append("唯一允许调 lv_* 的地方")
            content[3].append((("page", name), f"页面 {name}", lines))
        for name in ui_modules:
            content[3].append((("uipub", name), name, ["UI 事件源 ctx: lvgl"]))

        # Model 行内容
        model_lines = []
        types = (data.get("types") or "").strip()
        if types:
            n = len([ln for ln in types.splitlines() if ln.strip()])
            model_lines.append(f"契约类型 types（{n} 行 C 代码）")
        for f in data["model"]:
            model_lines.append(f"字段 {f.get('name', '?')}: {f.get('type', '?')}")
        for st in data["setters"]:
            suffix = f" → {st['event']}" if st.get("event") else "（只写不发）"
            model_lines.append(f"set_{st.get('name', '?')}(){suffix}")

        return model_lines, content

    def _collect_edges(self, data):
        """整理连线列表：[{kind, src, dst, label}, ...]（同类标签只标第一条）。"""
        edges = []
        for evt in data["events"]:
            evt_key = ("event", evt.get("id", "?"))
            for pub in evt.get("publishers") or []:
                if pub.get("context") == "lvgl":
                    edges.append({"kind": "uipub",
                                  "src": ("uipub", pub.get("module", "?")),
                                  "dst": evt_key, "label": "发布"})
                else:
                    edges.append({"kind": "forward",
                                  "src": ("pub", pub.get("module", "?")),
                                  "dst": evt_key, "label": "发布"})
            for sub in evt.get("subscribers") or []:
                if sub.get("handler"):
                    edges.append({"kind": "forward", "src": evt_key,
                                  "dst": ("handler", sub["handler"]),
                                  "label": "LVGL 投递"})
                elif sub.get("task"):
                    edges.append({"kind": "back", "src": evt_key,
                                  "dst": ("task", sub["task"]), "label": "入队"})
        first_setter = True
        for st in data["setters"]:
            if st.get("event"):
                edges.append({"kind": "model", "src": ("model",),
                              "dst": ("event", st["event"]),
                              "label": "写状态后发事件" if first_setter else ""})
                first_setter = False
        pages = [("page", p.get("page", "?")) for p in data["view_interfaces"]]
        if pages:
            first_call = True
            for evt in data["events"]:
                for sub in evt.get("subscribers") or []:
                    if sub.get("handler"):
                        for page_key in pages:
                            edges.append({"kind": "forward",
                                          "src": ("handler", sub["handler"]),
                                          "dst": page_key,
                                          "label": "调用接口" if first_call else ""})
                            first_call = False
        # 丢弃两端框不存在的边（悬空引用）
        return [e for e in edges
                if e["src"] in self._boxes and e["dst"] in self._boxes]

    # ================= 绘制 =================

    def refresh(self, data):
        """按当前文档数据全量重绘。"""
        self.scene.clear()
        self._boxes = {}
        self._header_rects = []
        self._label_rects = []
        model_lines, content = self._collect(data)
        self._fit_col_widths(content, model_lines)

        total_w = sum(self._col_w) + _COL_GAP * (len(COLS) - 1)

        # ---- Model 行（独占整行，宽=四列总宽，高按内容）----
        model_bottom = self._add_model_box(model_lines, total_w)

        # ---- Model 下方走线带（Model 边与 UI 事件源回边共用）+ 列标题带 ----
        n_model_edges = sum(1 for st in data["setters"] if st.get("event"))
        n_ui_edges = sum(1 for evt in data["events"]
                         for pub in evt.get("publishers") or []
                         if pub.get("context") == "lvgl")
        strip_h = _STRIP_TOP + _STRIP_STEP * max(1, n_model_edges + n_ui_edges) + 4
        header_y = model_bottom + strip_h

        bold = QFont()
        bold.setBold(True)
        for i, (title, _color, _hint) in enumerate(COLS):
            text = self.scene.addText(title, bold)
            text.setPos(self._col_x(i) + _MARGIN, header_y + 6)
            self._header_rects.append(
                QRectF(self._col_x(i), header_y, self._col_w[i], _HEADER_H))

        # ---- 四列框体 ----
        body_y = header_y + _HEADER_H
        max_y = body_y
        for col in range(len(COLS)):
            y = body_y
            if not content[col]:
                y = self._add_placeholder(col, y)
            for key, title, lines in content[col]:
                y = self._add_box(col, y, key, title, lines)
            max_y = max(max_y, y)

        # ---- 列背景（最底层）----
        for i, (_title, color, _hint) in enumerate(COLS):
            rect = self.scene.addRect(
                self._col_x(i), header_y, self._col_w[i],
                max_y - header_y + _MARGIN,
                QPen(QColor("#c0c0c0")), QBrush(QColor(color)))
            rect.setZValue(-1)

        # ---- 连线 ----
        # 走线带槽位：Model 边在前，UI 事件源回边在后；Model 边另记自身序号
        # （底缘出点分散用）
        edges = self._collect_edges(data)
        model_edges = [e for e in edges if e["kind"] == "model"]
        for i, e in enumerate(model_edges):
            e["strip_idx"] = i
            e["strip_n"] = max(1, len(model_edges))
        strip_idx = 0
        for e in edges:
            if e["kind"] in ("model", "uipub"):
                e["strip_y"] = model_bottom + _STRIP_TOP + strip_idx * _STRIP_STEP
                strip_idx += 1
        for e in edges:
            self._draw_edge(e)

        self.scene.setSceneRect(self.scene.itemsBoundingRect().adjusted(
            -_MARGIN, -_MARGIN, _MARGIN, _MARGIN))

    # ---- 测量 ----

    @staticmethod
    def _measure_lines(title, lines):
        """实测文本尺寸：返回 (内容宽, 内容高, 截断后明细行, 标题字体, 明细字体)。"""
        title_font = QFont()
        title_font.setBold(True)
        line_font = QFont()
        fm_t = QFontMetrics(title_font)
        fm = QFontMetrics(line_font)
        shown = [fm.elidedText(line, Qt.ElideRight, _TEXT_MAX_W)
                 for line in lines]
        text_w = fm_t.horizontalAdvance(title)
        for line in shown:
            text_w = max(text_w, fm.horizontalAdvance(line))
        height = (fm_t.height() + _TITLE_GAP + fm.height() * len(shown))
        return text_w, height, shown, title_font, line_font

    def _fit_col_widths(self, content, model_lines):
        """列宽 = 该列最宽框 + 两侧边距（文本已截断，不超 _TEXT_MAX_W）。"""
        fm = QFontMetrics(QFont())
        for col, boxes in content.items():
            need = _COL_MIN_W
            for _key, title, lines in boxes:
                text_w, _h, _s, _tf, _lf = self._measure_lines(title, lines)
                need = max(need, text_w + 2 * (_MARGIN + _BOX_PAD))
            hint = fm.horizontalAdvance(
                fm.elidedText(COLS[col][2], Qt.ElideRight, _TEXT_MAX_W))
            need = max(need, hint + 2 * _MARGIN)
            self._col_w[col] = need

    def _col_x(self, col):
        return _MARGIN + sum(self._col_w[:col]) + col * _COL_GAP

    def _gap_mid_x(self, col):
        """第 col 列与其右邻列间隙的中线 x（间隙内无框）。"""
        return self._col_x(col) + self._col_w[col] + _COL_GAP / 2

    # ---- 框与占位 ----

    def _add_model_box(self, lines, total_w):
        """Model 独占整行：宽度=四列总宽，高度按内容。返回底缘 y。"""
        if not lines:
            lines = ["契约类型、状态字段、写接口会出现在这里"]
        text_w, content_h, shown, title_font, line_font = self._measure_lines(
            "mvl_state_t 状态中心", lines)
        box_w = max(total_w, text_w + 2 * _BOX_PAD)
        box_h = content_h + 2 * _BOX_PAD
        x, y = _MARGIN, _MARGIN
        path = QPainterPath()
        path.addRoundedRect(QRectF(x, y, box_w, box_h), 6, 6)
        self.scene.addPath(path, QPen(QColor("#2e7d32"), 2),
                           QBrush(QColor("#eafaf0")))
        t = self.scene.addText("mvl_state_t 状态中心", title_font)
        t.setPos(x + _BOX_PAD, y + _BOX_PAD)
        fm = QFontMetrics(line_font)
        line_y = y + _BOX_PAD + QFontMetrics(title_font).height() + _TITLE_GAP
        for i, line in enumerate(shown):
            item = self.scene.addText(line, line_font)
            item.setDefaultTextColor(QColor("#444444"))
            item.setPos(x + _BOX_PAD, line_y + fm.height() * i)
        self._boxes[("model",)] = (-1, QRectF(x, y, box_w, box_h))
        return y + box_h

    def _add_box(self, col, y, key, title, lines):
        """画一个圆角矩形框（宽度按自身内容实测），返回底边 y。"""
        text_w, content_h, shown, title_font, line_font = self._measure_lines(
            title, lines)
        box_w = text_w + 2 * _BOX_PAD
        box_h = content_h + 2 * _BOX_PAD
        x = self._col_x(col) + _MARGIN
        path = QPainterPath()
        path.addRoundedRect(QRectF(x, y, box_w, box_h), 6, 6)
        self.scene.addPath(path, QPen(QColor("#555555")),
                           QBrush(QColor("white")))
        t = self.scene.addText(title, title_font)
        t.setPos(x + _BOX_PAD, y + _BOX_PAD)
        fm = QFontMetrics(line_font)
        line_y = y + _BOX_PAD + QFontMetrics(title_font).height() + _TITLE_GAP
        for i, line in enumerate(shown):
            item = self.scene.addText(line, line_font)
            item.setDefaultTextColor(QColor("#444444"))
            item.setPos(x + _BOX_PAD, line_y + fm.height() * i)
        self._boxes[key] = (col, QRectF(x, y, box_w, box_h))
        return y + box_h + _BOX_GAP

    def _add_placeholder(self, col, y):
        fm = QFontMetrics(QFont())
        text = fm.elidedText(COLS[col][2], Qt.ElideRight, _TEXT_MAX_W)
        item = self.scene.addText(text)
        item.setDefaultTextColor(QColor("#999999"))
        item.setPos(self._col_x(col) + _MARGIN, y)
        return y + fm.height() * 2

    # ---- 连线（全部走间隙/走线带，不穿框） ----

    def _edge_points(self, e):
        """计算折线顶点序列与标签锚点（首个水平段中点）。"""
        _ca, ra = self._boxes[e["src"]]
        _cb, rb = self._boxes[e["dst"]]
        if e["kind"] == "forward":
            # 出源右缘 → 间隙折线 → 入目标左缘
            la = self._boxes[e["src"]][0]
            gx = self._gap_mid_x(la)
            pts = [QPointF(ra.right(), ra.center().y()),
                   QPointF(gx, ra.center().y()),
                   QPointF(gx, rb.center().y()),
                   QPointF(rb.left(), rb.center().y())]
            anchor = QLineF(pts[0], pts[1]).pointAt(0.5)
        elif e["kind"] == "back":
            # 回边：出源左缘 → 间隙（x 右偏、y 下移，与正向线错开）→ 入目标右缘
            gx = self._gap_mid_x(0) + 12
            pts = [QPointF(ra.left(), ra.center().y() + 6),
                   QPointF(gx, ra.center().y() + 6),
                   QPointF(gx, rb.center().y() + 6),
                   QPointF(rb.right(), rb.center().y() + 6)]
            anchor = QLineF(pts[0], pts[1]).pointAt(0.5)
        elif e["kind"] == "uipub":
            # UI 事件源回边（第四列→第二列）：出顶缘 → 上行入走线带 →
            # 线带内水平左跨 → 事件列右间隙下行（错开正向折线 12px）→
            # 入事件框右缘（y 下移 6px 与同边正向出线错开）
            gx = self._gap_mid_x(1) + 12
            pts = [QPointF(ra.center().x(), ra.top()),
                   QPointF(ra.center().x(), e["strip_y"]),
                   QPointF(gx, e["strip_y"]),
                   QPointF(gx, rb.center().y() + 6),
                   QPointF(rb.right(), rb.center().y() + 6)]
            anchor = QLineF(pts[1], pts[2]).pointAt(0.5)
        else:  # model：底缘分散出点 → 走线带 → 列间隙 → 入事件框左缘
            _cm, rm = self._boxes[("model",)]
            # 出点在 Model 底缘、事件列水平范围内分散
            span_l = self._col_x(1) + _MARGIN
            span_r = self._col_x(1) + self._col_w[1] - _MARGIN
            frac = (e["strip_idx"] + 1) / (e["strip_n"] + 1)
            x0 = span_l + frac * (span_r - span_l)
            gx = self._gap_mid_x(0) - 12
            pts = [QPointF(x0, rm.bottom()),
                   QPointF(x0, e["strip_y"]),
                   QPointF(gx, e["strip_y"]),
                   QPointF(gx, rb.center().y()),
                   QPointF(rb.left(), rb.center().y())]
            anchor = QLineF(pts[1], pts[2]).pointAt(0.5)
        return pts, anchor

    def _draw_edge(self, e):
        pen = QPen(QColor("#336699"))
        pen.setWidth(2)
        pts, anchor = self._edge_points(e)
        for a, b in zip(pts, pts[1:]):
            self.scene.addLine(QLineF(a, b), pen)
        self._arrowhead(pts[-2], pts[-1], pen)
        if e["label"]:
            self._add_arrow_label(anchor, e["label"])

    def _add_arrow_label(self, anchor, text):
        """在所属线段附近画带不透明底色的标签。

        候选位置是锚点周围的有界集合：线上居中（文字骑线，底色盖线）→
        线上方 → 线下方 → 各候选再左右滑移。避让检测范围：所有框体 +
        列标题带 + 已放置标签；全部候选都冲突则省略该标签——
        不允许为避让而远离所属线段。
        """
        fm = QFontMetrics(QFont())
        w = fm.horizontalAdvance(text)
        h = fm.height()
        candidates = []
        for dy in (-h / 2, -(4 + h), 4.0):      # 线上 / 上方 / 下方
            candidates.append((0.0, dy))
        for dx in (-(w / 2 + 14), w / 2 + 14):  # 沿线左右滑移（骑线）
            candidates.append((dx, -h / 2))
        for dx in (-30.0, 30.0):                # 上/下方再左右滑移
            candidates.append((dx, -(4 + h)))
            candidates.append((dx, 4.0))
        for dx, dy in candidates:
            x = anchor.x() - w / 2 + dx
            y = anchor.y() + dy
            rect = QRectF(x - 2, y - 1, w + 4, h + 2)
            blocked = (any(rect.intersects(r) for _c, r in self._boxes.values())
                       or any(rect.intersects(r) for r in self._header_rects)
                       or any(rect.intersects(r) for r in self._label_rects))
            if not blocked:
                bg = self.scene.addRect(rect, QPen(Qt.NoPen),
                                        QBrush(QColor(_LABEL_BG)))
                bg.setZValue(1)
                item = self.scene.addText(text)
                item.setDefaultTextColor(QColor("#336699"))
                item.setPos(x, y)
                item.setZValue(2)
                self._label_rects.append(rect)
                return
        # 线段附近放不下：省略该标签

    def _arrowhead(self, p1, p2, pen):
        line = QLineF(p1, p2)
        if line.length() < 1:
            return
        angle = math.atan2(-line.dy(), line.dx())
        size = 8
        a1 = angle + math.pi * 0.85
        a2 = angle - math.pi * 0.85
        head = QPolygonF([
            p2,
            p2 + QPointF(math.cos(a1) * size, -math.sin(a1) * size),
            p2 + QPointF(math.cos(a2) * size, -math.sin(a2) * size),
        ])
        self.scene.addPolygon(head, pen, QBrush(QColor("#336699")))
