"""
将 outputs/knowledge.jsonl 转为 CSV（kid, topic, subtopic, title, content, keywords）。
keywords 为 JSON 数组，导出时合并为单列（默认用「; 」连接）。
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def parse_args() -> argparse.Namespace:
    root = _repo_root()
    p = argparse.ArgumentParser(description="将 knowledge.jsonl 转为 CSV")
    p.add_argument(
        "-i",
        "--input",
        type=Path,
        default=root / "outputs" / "knowledge.jsonl",
        help="输入 JSONL 路径",
    )
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="输出 CSV 路径（默认与输入同目录下的 knowledge.csv）",
    )
    p.add_argument(
        "--keyword-sep",
        default="; ",
        help="keywords 数组合并为字符串时使用的分隔符",
    )
    p.add_argument(
        "--utf8-bom",
        action="store_true",
        help="使用 utf-8-sig 写入，便于 Excel 直接打开中文列",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    inp: Path = args.input
    out: Path = args.output or (inp.parent / "knowledge.csv")
    encoding = "utf-8-sig" if args.utf8_bom else "utf-8"

    if not inp.is_file():
        print(f"错误：找不到输入文件 {inp}", file=sys.stderr)
        return 1

    out.parent.mkdir(parents=True, exist_ok=True)
    fields = ["kid", "topic", "subtopic", "title", "content", "keywords"]

    with inp.open("r", encoding="utf-8") as fin, out.open(
        "w", newline="", encoding=encoding
    ) as fout:
        writer = csv.DictWriter(fout, fieldnames=fields, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        for line_no, line in enumerate(fin, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"错误：第 {line_no} 行 JSON 解析失败：{e}", file=sys.stderr)
                return 1
            kw = obj.get("keywords")
            if isinstance(kw, list):
                kw_str = args.keyword_sep.join(str(x) for x in kw)
            elif kw is None:
                kw_str = ""
            else:
                kw_str = str(kw)
            writer.writerow(
                {
                    "kid": obj.get("kid", ""),
                    "topic": obj.get("topic", ""),
                    "subtopic": obj.get("subtopic", ""),
                    "title": obj.get("title", ""),
                    "content": obj.get("content", ""),
                    "keywords": kw_str,
                }
            )

    print(f"已写入：{out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
