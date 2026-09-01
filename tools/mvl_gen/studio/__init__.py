"""mvl_gen.studio —— mvl-studio 图形化编辑器。

GUI 只是 YAML 的薄编辑器：数据模型与 YAML 往返逻辑在 document.py
（可无头测试），PySide6 界面在 main_window.py。
"""

from .document import StudioDocument, IssueView

__all__ = ["StudioDocument", "IssueView"]
