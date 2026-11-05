"""Compile per-paper reading cards into a navigable domain graph.

Deterministic and mechanical: equal names are merged case-insensitively, nothing
is inferred. The domain expert reads these files on demand instead of every
full reading record, and its structured landscape is checked against them.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .storage import write_json


def _key(label: str) -> str:
    return " ".join(label.lower().split())


def _slug(label: str) -> str:
    readable = re.sub(r"[^a-z0-9]+", "-", _key(label)).strip("-")[:40] or "problem"
    return f"{readable}-{hashlib.sha256(_key(label).encode()).hexdigest()[:8]}"


def compile_graph(cards: dict[str, dict], titles: dict[str, str]) -> dict:
    problems: dict[str, dict] = {}
    methods: dict[str, dict] = {}
    results, relations, external = [], [], []
    for paper_id, card in cards.items():
        problem = problems.setdefault(_key(card["problem"]), {"label": card["problem"], "paper_ids": []})
        problem["paper_ids"].append(paper_id)
        for item in card["contributions"]:
            method = methods.setdefault(
                _key(item["method"]), {"label": item["method"], "paper_ids": [], "problems": []}
            )
            method["paper_ids"].append(paper_id)
            if _key(card["problem"]) not in method["problems"]:
                method["problems"].append(_key(card["problem"]))
            results.extend(
                dict(result, paper_id=paper_id, method=item["method"]) for result in item["results"]
            )
        for relation in card["relations"]:
            (relations if relation["paper_id"] in cards else external).append(dict(relation, source=paper_id))
    return {
        "papers": {pid: titles.get(pid, pid) for pid in cards},
        "problems": problems,
        "methods": methods,
        "results": results,
        "relations": relations,
        "external_relations": external,
    }


def write_views(folder: Path, graph: dict, cards: dict[str, dict]) -> dict:
    """graph.json, an index, and one file of cards per problem for progressive reading."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "problems").mkdir(exist_ok=True)
    write_json(folder / "graph.json", graph)
    lines = [
        "# 领域图谱索引",
        "",
        "由逐篇阅读的论文卡机械合并而成（同名不区分大小写合并），未做推断。",
        "",
        f"论文 {len(graph['papers'])} 篇；问题 {len(graph['problems'])} 个；方法 {len(graph['methods'])} 个；"
        f"结果记录 {len(graph['results'])} 条；语料内关系 {len(graph['relations'])} 条。",
        "",
        "| 论文 | 方法 | 问题（摘要） | 文件 |",
        "| --- | --- | --- | --- |",
    ]
    for key, problem in sorted(graph["problems"].items(), key=lambda kv: -len(kv[1]["paper_ids"])):
        name = f"problems/{_slug(key)}.md"
        methods = "; ".join(
            item["method"][:60] for pid in problem["paper_ids"] for item in cards[pid]["contributions"]
        )
        label = problem["label"].replace("|", "/")
        lines.append(
            f"| {', '.join(problem['paper_ids'])} | {methods} | {label[:140]}{'…' if len(label) > 140 else ''} | `{name}` |"
        )
        body = [f"# {problem['label']}", ""]
        for paper_id in problem["paper_ids"]:
            card = cards[paper_id]
            body.append(f"## {paper_id}：{graph['papers'][paper_id]}")
            for item in card["contributions"]:
                body.append(f"- 方法：{item['method']}；机制：{item['mechanism']}")
                body.extend(f"  - 假设：{text}" for text in item["assumptions"])
                body.extend(
                    f"  - 结果：{r['benchmark']} / {r['metric']} = {r['value']}（条件：{r['condition']}）"
                    for r in item["results"]
                )
            body.extend(
                f"- 关系：{r['relation']} → {r['paper_id']}（{r['note']}）" for r in card["relations"]
            )
            body.append("")
        (folder / name).write_text("\n".join(body), encoding="utf-8")
    (folder / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "index": str(folder / "index.md"),
        "graph": str(folder / "graph.json"),
        "problems_dir": str(folder / "problems"),
    }
