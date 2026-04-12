"""CSV 导出：正确处理引号、逗号与换行。"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, Mapping


def write_query_answer_csv(rows: Iterable[Mapping[str, str]], path: Path) -> None:
    """
    写入标准 CSV，表头为 query,answer。
    使用 csv.writer 处理特殊字符。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        w.writerow(["query", "answer"])
        for r in rows:
            w.writerow([r.get("query", ""), r.get("answer", "")])
