"""cli.py —— mvl-gen 命令行入口。

    mvl-gen check    <yaml>            只做静态检查，有错误时非零退出
    mvl-gen generate <yaml> -o <dir>   生成 C 骨架代码 + wiring_report.md
    mvl-gen diagram  <yaml> -o <file>  导出 mermaid 接线图（Markdown）
"""

import argparse
import sys

from . import __version__
from .checks import format_issues, has_errors, run_checks
from .codegen import generate
from .diagram import export_diagram
from .ir import IrError, load_ir


def _load_and_check(yaml_path):
    """加载 IR 并跑静态检查；结构非法时抛 IrError。"""
    ir = load_ir(yaml_path)
    issues = run_checks(ir)
    return ir, issues


def _print_issues(issues, stream):
    if issues:
        print(format_issues(issues), file=stream)
    else:
        print("静态检查全部通过（C1~C4 / C7 / C8；C5/C6 由生成器构造保证）",
              file=stream)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="mvl-gen",
        description="MVL (MVVM-Lite) 接线设计代码生成工具")
    parser.add_argument("--version", action="version",
                        version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check", help="只做静态检查，有错误时非零退出")
    p_check.add_argument("yaml", help="mvl_project.yaml 路径")

    p_gen = sub.add_parser("generate", help="生成 C 骨架代码与接线报告")
    p_gen.add_argument("yaml", help="mvl_project.yaml 路径")
    p_gen.add_argument("-o", "--out", required=True, help="输出目录")

    p_dia = sub.add_parser("diagram", help="导出 mermaid 接线图")
    p_dia.add_argument("yaml", help="mvl_project.yaml 路径")
    p_dia.add_argument("-o", "--out", required=True, help="输出 Markdown 文件")

    args = parser.parse_args(argv)

    try:
        ir, issues = _load_and_check(args.yaml)
    except IrError as e:
        print(f"YAML 结构错误: {e}", file=sys.stderr)
        return 2
    except FileNotFoundError:
        print(f"文件不存在: {args.yaml}", file=sys.stderr)
        return 2

    if args.command == "check":
        _print_issues(issues, sys.stdout)
        return 1 if has_errors(issues) else 0

    if args.command == "generate":
        _print_issues(issues, sys.stdout)
        if has_errors(issues):
            print("存在检查错误，已中止生成（先修正 YAML 或运行 check 查看）",
                  file=sys.stderr)
            return 1
        written = generate(ir, issues, args.out)
        for path in written:
            print(f"生成: {path}")
        return 0

    if args.command == "diagram":
        _print_issues(issues, sys.stdout)
        if has_errors(issues):
            print("存在检查错误，已中止导出", file=sys.stderr)
            return 1
        export_diagram(ir, args.out)
        print(f"生成: {args.out}")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
