"""studio/app.py —— mvl-studio 入口。"""

import sys


def main(argv=None):
    from PySide6.QtWidgets import QApplication

    from .document import StudioDocument
    from .main_window import MainWindow

    argv = list(sys.argv if argv is None else argv)
    app = QApplication(argv)
    app.setApplicationName("mvl-studio")

    # 命令行可带一个 yaml 路径直接打开
    path = next((a for a in argv[1:] if not a.startswith("-")), None)
    doc = StudioDocument.load(path) if path else StudioDocument.new_from_template()

    win = MainWindow(doc)
    if path:
        win.setWindowTitle(f"mvl-studio —— {path}")
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
