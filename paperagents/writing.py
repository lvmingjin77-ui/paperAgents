"""Evidence-bound LaTeX documents, frozen research snapshots and local compilation."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import subprocess
from pathlib import Path

from .storage import digest, read_json, write_json

_ID = re.compile(r"^[A-Za-z0-9_.@:/-]+$")
_CITE = re.compile(r"\\cite\w*\*?(?:\[[^]]*\])*\{([^}]+)\}")
_METRIC = re.compile(r"\\metric\{([^}]+)\}\{([^}]+)\}")
_PRIMITIVES = re.compile(r"\\(?:write18|openin|openout|read|write|catcode|immediate|directlua)(?![A-Za-z])")
_DANGEROUS = re.compile(
    r"\\(?:write18|openin|openout|read|write|catcode|immediate|directlua|input|include|usepackage|documentclass)(?![A-Za-z])"
)
_FILE_COMMAND = re.compile(
    r"\\(input|include|includegraphics|bibliography|bibliographystyle|lstinputlisting|verbatiminput)\*?(?:\[[^]]*\])*\{([^}]+)\}"
)


def _tex(text: object) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "{": r"\{",
        "}": r"\}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(c, c) for c in str(text))


def metric_catalog(state: dict) -> list[dict]:
    """Numbers come from executed, protocol-valid runs, never from writer output."""
    catalog = []
    for run_id, run in state.get("runs", {}).items():
        if run.get("outcome") != "completed":
            continue
        for name, value in run.get("metrics", {}).items():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                continue
            if not _ID.fullmatch(run_id) or not _ID.fullmatch(name):
                raise ValueError("Run and metric identifiers must be safe LaTeX macro identifiers")
            catalog.append(
                {
                    "run_id": run_id,
                    "metric": name,
                    "value": value,
                    "claim_ref": run.get("claim_ref"),
                    "split": run.get("split"),
                    "seed": run.get("seed"),
                    "macro": f"\\metric{{{run_id}}}{{{name}}}",
                }
            )
    # Unit-bootstrap summaries: \metric{<comparison evidence>}{<baseline>.<metric>.<series>.<est|lo|hi>}
    for eid, evidence in state.get("evidence", {}).items():
        if evidence["kind"] != "comparison":
            continue
        content = evidence["content"]
        for baseline, report in content["baselines"].items():
            for metric, rows in report["unit_bootstrap"].items():
                for series in ("baseline", "candidate", "improvement"):
                    estimate, interval = rows[series]
                    for stat, value in zip(("est", "lo", "hi"), [estimate, *(interval or [None, None])]):
                        if value is None:
                            continue
                        name = f"{baseline}.{metric}.{series}.{stat}"
                        if not _ID.fullmatch(name):
                            raise ValueError("Baseline and metric identifiers must be safe LaTeX macro identifiers")
                        catalog.append(
                            {
                                "run_id": eid,
                                "metric": name,
                                "value": value,
                                "claim_ref": evidence["claim_ref"],
                                "split": content["split"],
                                "n_units": rows["n_units"],
                                "macro": f"\\metric{{{eid}}}{{{name}}}",
                            }
                        )
    return catalog


def generate_figures(run_dir: Path, state: dict) -> list[dict]:
    """Plot recorded executions, separating protocols, splits and implementation versions."""
    groups = {}
    for run_id, run in state.get("runs", {}).items():
        if run.get("outcome") != "completed" or not all(
            run.get(k) for k in ("protocol_id", "protocol_hash", "code_hash", "program", "split")
        ):
            continue
        if run.get("claim_ref") and run["claim_ref"] not in state.get("claims", {}):
            continue
        for metric, value in run.get("metrics", {}).items():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                continue
            key = (run["protocol_id"], run["protocol_hash"], run["split"], metric)
            groups.setdefault(key, {})[run_id] = run
    figures = []
    for (protocol_id, protocol_hash, split, metric), runs in sorted(groups.items()):
        if not any(not r.get("claim_ref") and r["program"] == "baseline" for r in runs.values()):
            continue
        if not any(r.get("claim_ref") in state.get("claims", {}) for r in runs.values()):
            continue
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure

        run_ids = sorted(runs)
        claim_refs = sorted({r["claim_ref"] for r in runs.values() if r.get("claim_ref")})
        evidence_ids = sorted(
            eid
            for eid, item in state.get("evidence", {}).items()
            if item.get("kind") == "run" and item.get("content", {}).get("run_id") in run_ids
        )
        sources = {
            rid: {
                key: runs[rid].get(key)
                for key in (
                    "claim_ref",
                    "program",
                    "code_hash",
                    "protocol_id",
                    "protocol_hash",
                    "split",
                    "seed",
                    "metrics",
                    "outcome",
                )
            }
            for rid in run_ids
        }
        source_hash = digest(sources)
        caption = (
            f"{metric} on {split}, protocol {protocol_id}. Each point is one completed execution. "
            "Rows separate claim and implementation versions; points are not confidence intervals or significance tests."
        )
        identity = digest({"sources": sources, "metric": metric})[:20]
        directory = Path(run_dir).resolve() / "paper" / "figures"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{identity}.pdf"
        preview = directory / f"{identity}.png"
        receipt_path = directory / f"{identity}.json"
        series = {}
        for rid in run_ids:
            run = runs[rid]
            key = (run.get("claim_ref") or "baseline", run["program"], run["code_hash"])
            series.setdefault(key, []).append(run)
        fig = Figure(figsize=(8, max(2.8, 1.6 + 0.55 * len(series))), layout="constrained")
        FigureCanvasAgg(fig)
        ax = fig.subplots()
        for row, (key, observations) in enumerate(sorted(series.items())):
            offset = [
                (i - (len(observations) - 1) / 2) * min(0.07, 0.3 / len(observations))
                for i in range(len(observations))
            ]
            ax.scatter(
                [item["metrics"][metric] for item in observations],
                [row + v for v in offset],
                color="#6b7280" if key[:2] == ("baseline", "baseline") else "#216653",
                s=32,
                alpha=0.85,
            )
        ax.set_yticks(
            range(len(series)),
            labels=[f"{claim} / {program} / {code[:8]}" for claim, program, code in sorted(series)],
        )
        ax.set_xlabel(metric)
        ax.set_title(f"{split} | {protocol_id}", loc="left")
        ax.grid(axis="x", color="#e5e7eb", linewidth=0.7)
        ax.set_axisbelow(True)
        ax.spines[["top", "right"]].set_visible(False)
        fig.savefig(path, metadata={"CreationDate": None, "ModDate": None})
        fig.savefig(preview, dpi=180)
        fig.clear()
        record = {
            "path": str(path),
            "preview_path": str(preview),
            "asset_path": f"assets/{path.name}",
            "claim_refs": claim_refs,
            "run_ids": run_ids,
            "evidence_ids": evidence_ids,
            "caption": caption,
            "protocol_id": protocol_id,
            "protocol_hash": protocol_hash,
            "split": split,
            "metric": metric,
            "source_hash": source_hash,
            "sources": sources,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "preview_sha256": hashlib.sha256(preview.read_bytes()).hexdigest(),
        }
        write_json(receipt_path, record)
        figures.append(record)
    write_json(Path(run_dir) / "paper" / "figures" / "index.json", {"figures": figures})
    return figures


def _literature(state: dict) -> list[dict]:
    papers = list(state.get("knowledge", {}).get("corpus", {}).get("papers", []))
    for record in state.get("evidence", {}).values():
        if record.get("kind") == "literature":
            source = record.get("source")
            if isinstance(source, dict):
                papers.append(source)
    return papers


def _reference_source(reference: dict, papers: list[dict]) -> dict:
    # A matching identifier locates a source; it does not validate the paper's claims.
    for paper in papers:
        if any(reference.get(key) and reference[key] == paper.get(key) for key in ("paper_id", "doi", "url")):
            if (
                reference.get("title")
                and paper.get("title")
                and reference["title"].casefold() != paper["title"].casefold()
            ):
                raise ValueError(f"Reference title disagrees with source: {reference['key']}")
            return paper
        if reference.get("title") and reference["title"].casefold() == str(paper.get("title", "")).casefold():
            return paper
    raise ValueError(f"Reference has no literature source: {reference['key']}")


def freeze_snapshot(state: dict, claim_refs: list[str]) -> dict:
    if not claim_refs or len(set(claim_refs)) != len(claim_refs):
        raise ValueError("Freeze requires distinct claim versions")
    claims = {ref: state["claims"][ref] for ref in claim_refs}
    runs = {
        key: item
        for key, item in state.get("runs", {}).items()
        if item.get("claim_ref") in claims and item.get("split") != "test"
    }
    snapshot = {
        "claims": claims,
        "claim_refs": list(claim_refs),
        "protocol": state.get("protocol", {}),
        "runs": runs,
        "evidence": {
            key: item for key, item in state.get("evidence", {}).items() if item.get("claim_ref") in claims
        },
    }
    # JSON copy prevents later mutations of live state from silently changing the freeze.
    return json.loads(json.dumps(dict(snapshot, hash=digest(snapshot))))


def update_outline(run_dir: Path, state: dict, config: dict) -> dict:
    """Keep an evidence index for W0/W1 without inventing manuscript prose."""
    claims = state.get("claims", {})
    evidence = state.get("evidence", {})
    metrics = [item for item in metric_catalog(state) if item["split"] != "test"]
    outline = {
        "protocol": state.get("protocol", {}),
        "claims": claims,
        "evidence": {
            eid: {key: item.get(key) for key in ("kind", "claim_ref", "source", "hash")}
            for eid, item in evidence.items()
        },
        "metrics": metrics,
        "references": _literature(state),
        "output": config.get("output", {}),
        "scope": state.get("knowledge", {}).get("scope", {}),
    }
    lines = [
        "# 论文工作提纲",
        "",
        "随研究状态更新；尚未验证的主张不是论文结论。",
        "",
        "## 问题与范围",
        "",
        "```json",
        json.dumps(outline["scope"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## 相关工作",
        "",
    ]
    lines.extend(
        f"- `{paper.get('paper_id', '')}`：{paper.get('title', '')}" for paper in outline["references"]
    )
    lines.extend(
        [
            "",
            "## 实验协议",
            "",
            "```json",
            json.dumps(outline["protocol"], ensure_ascii=False, indent=2),
            "```",
            "",
            "## 主张、论证与证据",
            "",
        ]
    )
    for ref, claim in claims.items():
        ids = [eid for eid, item in evidence.items() if item.get("claim_ref") == ref]
        lines.extend(
            [
                f"### {ref}",
                "",
                str(claim.get("text", "")),
                "",
                f"- 状态：{claim.get('verdict', 'untested')}；作者：{claim.get('owner', '')}",
                "- 来源版本：" + ", ".join(claim.get("parents", [])),
                "- 证据：" + (", ".join(f"`{eid}`" for eid in ids) or "尚无证据"),
                "",
            ]
        )
    lines.extend(["## 开发集测量值", "", "只记录运行器产出的数字；失败运行与封存测试不进入此提纲。", ""])
    lines.extend(
        f"- `{item['macro']}` = {item['value']:.8g}；主张 `{item['claim_ref'] or 'baseline'}`；"
        + (f"seed {item['seed']}" if "seed" in item else f"{item['n_units']} 个统计单位的汇总")
        for item in metrics
    )
    lines.extend(["", "## 待完成论证", "", "作者根据证据撰写段落；独立评审核验论证。未解决项保持开放。", ""])
    directory = Path(run_dir) / "paper"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "outline.md"
    text = "\n".join(lines)
    if not path.is_file() or path.read_text() != text:
        path.write_text(text)
    write_json(directory / "outline.json", outline)
    return {
        "path": str(path.resolve()),
        "index": str((directory / "outline.json").resolve()),
        "hash": digest(outline),
        "claim_refs": list(claims),
        "evidence_ids": list(evidence),
    }


def materialize_draft(run_dir: Path, state: dict, content: dict, config: dict) -> dict:
    """Publish a versioned draft. Semantic claims remain the authors/reviewers' responsibility."""
    title, sections = content.get("title", ""), content.get("sections", [])
    if not title or not sections:
        raise ValueError("Draft requires a title and sections")
    claims = state.get("claims", {})
    references = content.get("references", [])
    keys = [ref["key"] for ref in references]
    if len(set(keys)) != len(keys) or any(not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", key) for key in keys):
        raise ValueError("References require unique safe keys")
    papers = _literature(state)
    reference_sources = {ref["key"]: _reference_source(ref, papers) for ref in references}
    metrics = metric_catalog(state)
    macro_ids = {(m["run_id"], m["metric"]) for m in metrics}
    files: dict[str, str] = {}
    template_files: dict[str, bytes] = {}
    assets: dict[str, bytes] = {}
    figure_sources = []
    bindings = []
    for index, section in enumerate(sections):
        refs, tex = section.get("claim_refs", []), section.get("tex", "")
        if not refs or any(ref not in claims for ref in refs):
            raise ValueError(f"Section {index} must bind existing claim versions")
        if not isinstance(tex, str) or _DANGEROUS.search(tex):
            raise ValueError("Section content cannot configure LaTeX or read/write external files")
        for group in _CITE.findall(tex):
            if not set(group.split(",")).issubset(keys):
                raise ValueError(f"Unknown citation: {group}")
        for run_id, metric in _METRIC.findall(tex):
            if (run_id, metric) not in macro_ids:
                raise ValueError(f"Unknown or invalid result: {run_id}/{metric}")
            source = state["runs"].get(run_id) or state["evidence"][run_id]
            run_ref = source.get("claim_ref")
            if run_ref and run_ref not in refs:
                raise ValueError(f"Result {run_id} belongs to an unbound claim version")
        name = f"sections/{index:02d}.tex"
        files[name] = (
            "% claim_refs: " + ", ".join(refs) + "\n\\section{" + _tex(section["name"]) + "}\n" + tex + "\n"
        )
        bindings.append({"path": name, "claim_refs": refs})
    for selection in content.get("figures", []):
        path = Path(selection["path"]).resolve()
        figure_root = Path(run_dir).resolve() / "paper" / "figures"
        if path.parent != figure_root or path.suffix != ".pdf" or not path.with_suffix(".json").is_file():
            raise ValueError("Figures must come from this run's generated figure catalog")
        source = read_json(path.with_suffix(".json"))
        if set(selection.get("claim_refs", [])) != set(source["claim_refs"]) or set(
            selection.get("run_ids", [])
        ) != set(source["run_ids"]):
            raise ValueError("Figure claim and execution bindings disagree with generated source")
        current = {
            rid: {key: state.get("runs", {}).get(rid, {}).get(key) for key in recorded}
            for rid, recorded in source["sources"].items()
        }
        if (
            digest(current) != source["source_hash"]
            or not path.is_file()
            or hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]
        ):
            raise ValueError("Figure or its recorded execution source changed")
        if any(ref not in claims for ref in source["claim_refs"]):
            raise ValueError("Figure refers to an unknown claim version")
        asset_name = "assets/" + path.name
        assets[asset_name] = path.read_bytes()
        figure_sources.append(dict(source, asset_path=asset_name))
        binding = next((b for b in bindings if set(source["claim_refs"]) <= set(b["claim_refs"])), None)
        if binding is None:
            binding = {"path": f"sections/{len(bindings):02d}.tex", "claim_refs": source["claim_refs"]}
            files[binding["path"]] = (
                "% claim_refs: " + ", ".join(source["claim_refs"]) + "\n\\section{Recorded comparisons}\n"
            )
            bindings.append(binding)
        files[binding["path"]] += (
            "\n\\begin{figure}[htbp]\n\\centering\n\\includegraphics[width=\\linewidth]{" + asset_name + "}\n"
            "\\caption{" + _tex(selection.get("caption") or source["caption"]) + "}\n\\end{figure}\n"
        )
    files["metrics.tex"] = "\\newcommand{\\metric}[2]{\\csname metric:#1:#2\\endcsname}\n" + "".join(
        f"\\expandafter\\def\\csname metric:{m['run_id']}:{m['metric']}\\endcsname{{{m['value']:.8g}}}\n"
        for m in metrics
    )
    bib = []
    for ref in references:
        source = reference_sources[ref["key"]]
        # Copy source metadata, rather than accepting new bibliographic facts from the writer.
        fields = {key: source.get(key, "") for key in ("title", "year", "doi", "url")}
        author = source.get("authors", [])
        fields["author"] = " and ".join(author) if isinstance(author, list) else author
        bib.append(
            "@misc{"
            + ref["key"]
            + ",\n"
            + ",\n".join(f"  {key} = {{{_tex(value)}}}" for key, value in fields.items() if value)
            + "\n}"
        )
    files["references.bib"] = "\n\n".join(bib) + "\n"
    output = config.get("output", {})
    template = output.get("template", "article")
    if template not in ("article", ""):
        template_dir = Path(template).expanduser()
        if not template_dir.is_absolute():
            template_dir = Path(run_dir).parents[1] / template_dir
        if not (template_dir / "header.tex").is_file():
            raise ValueError(
                "output.template must be article or a local template directory containing header.tex"
            )
        for path in template_dir.rglob("*"):
            if path.is_file() and path.suffix in {".sty", ".cls", ".bst", ".tex"}:
                if path.is_symlink():
                    raise ValueError("Template files must be regular local files")
                template_files[path.relative_to(template_dir).as_posix()] = path.read_bytes()
    author = (
        "Anonymous Authors" if output.get("anonymous", True) else output.get("authors", "PaperAgents Authors")
    )
    files["main.tex"] = (
        "\\documentclass[11pt]{article}\n\\usepackage[utf8]{inputenc}\n"
        "\\usepackage[T1]{fontenc}\n\\usepackage{amsmath,graphicx,booktabs,url}\n"
        "\\input{metrics.tex}\n\\title{" + _tex(title) + "}\n\\author{" + _tex(author) + "}\n"
        "\\date{}\n\\begin{document}\n\\maketitle\n"
        + "".join("\\input{" + b["path"] + "}\n" for b in bindings)
        + "\\bibliographystyle{plain}\n\\bibliography{references}\n\\end{document}\n"
    )
    if template_files:
        header = template_files.pop("header.tex").decode()
        if "\\begin{document}" not in header:
            raise ValueError("Template header.tex must contain the preamble and begin{document}")
        header = header.replace("%%PAPERAGENTS_TITLE%%", _tex(title)).replace(
            "%%PAPERAGENTS_AUTHORS%%", _tex(author)
        )
        header = header.replace(
            "\\begin{document}", "\\usepackage{graphicx}\n\\input{metrics.tex}\n\\begin{document}"
        )
        footer = template_files.pop(
            "footer.tex", b"\\bibliographystyle{plain}\n\\bibliography{references}\n\\end{document}\n"
        ).decode()
        files["main.tex"] = header + "\n" + "".join("\\input{" + b["path"] + "}\n" for b in bindings) + footer
    if set(template_files).intersection(set(files) | set(assets)) or "claims.json" in template_files:
        raise ValueError("Template files conflict with generated manuscript files")
    manifest = {
        "title": title,
        "bindings": bindings,
        "claims": {ref: claims[ref] for b in bindings for ref in b["claim_refs"]},
        "metrics": metrics,
        "reference_sources": reference_sources,
        "figures": figure_sources,
        "venue": output.get("venue", ""),
        "template": str(template or "article"),
        "anonymous": output.get("anonymous", True),
        "page_limit": output.get("page_limit"),
        "frozen_hash": state.get("frozen", {}).get("hash"),
        "files": {
            **{name: hashlib.sha256(text.encode()).hexdigest() for name, text in files.items()},
            **{name: hashlib.sha256(data).hexdigest() for name, data in (template_files | assets).items()},
        },
    }
    version = digest(manifest)[:20]
    directory = Path(run_dir) / "paper" / version
    directory.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_text() != text:
            raise ValueError("Published draft contents changed")
        path.write_text(text)
    for name, data in (template_files | assets).items():
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    write_json(directory / "claims.json", manifest)
    result = {
        "path": str(directory.resolve()),
        "main": str((directory / "main.tex").resolve()),
        "version": version,
        "hash": digest(manifest),
        "audit": audit_draft(directory),
    }
    write_json(Path(run_dir) / "paper" / "latest.json", result)
    return result


def audit_draft(draft_dir: Path) -> dict:
    directory = Path(draft_dir)
    manifest = read_json(directory / "claims.json")
    errors, notes = [], []
    for figure in manifest.get("figures", []):
        path = Path(figure["path"])
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != figure["sha256"]:
            errors.append(f"Figure source changed: {path.name}")
        if digest(figure["sources"]) != figure["source_hash"]:
            errors.append(f"Figure execution receipt changed: {path.name}")
    for name, expected in manifest["files"].items():
        path = directory / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            errors.append(f"Source changed: {name}")
            continue
        if path.suffix != ".tex" or name == "metrics.tex":
            continue
        text = path.read_text()
        if _PRIMITIVES.search(text):
            errors.append(f"Direct TeX file or process operations are not allowed: {name}")
        if re.search(r"\\(?:input|include)\b\s+(?!\{)", text):
            errors.append(f"File inputs must name an explicit manuscript artifact in braces: {name}")
        for command, value in _FILE_COMMAND.findall(text):
            for target in value.split(","):
                candidate = Path(target.strip())
                if (
                    candidate.is_absolute()
                    or any(part.startswith(".") for part in candidate.parts)
                    or "\\" in target
                ):
                    errors.append(f"External or dynamic input is not allowed: {name}: {target}")
                    continue
                if command == "bibliographystyle" and re.fullmatch(r"[A-Za-z0-9_-]+", target):
                    continue  # Installed bibliography styles are resolved by TeX.
                choices = [candidate.as_posix()] + [
                    candidate.as_posix() + ext for ext in (".tex", ".bib", ".pdf", ".png", ".jpg")
                ]
                if not any(choice in manifest["files"] for choice in choices):
                    errors.append(f"Input has no manuscript artifact receipt: {name}: {target}")
        for packages in re.findall(r"\\(?:usepackage|documentclass)(?:\[[^]]*\])*\{([^}]+)\}", text):
            if any(not re.fullmatch(r"[A-Za-z0-9_-]+", package.strip()) for package in packages.split(",")):
                errors.append(f"Package or class must use an installed or local name: {name}")
    notes.append(
        "Source existence, numeric provenance and version bindings are checked; semantic support requires peer review."
    )
    for binding in manifest["bindings"]:
        path = directory / binding["path"]
        if not path.is_file():
            continue
        text = path.read_text()
        if re.search(r"(?<![A-Za-z])\d+(?:\.\d+)?\s*(?:\\%|%)", text):
            notes.append(
                f"Unbound percentage needs review in {binding['path']}; use metric macros for measured results."
            )
    return {"passed": not errors, "errors": errors, "notes": notes, "page_limit_checked": False}


def compile_draft(draft_dir: Path) -> dict:
    """Compile locally with shell escapes disabled. No installation or network access is attempted."""
    directory = Path(draft_dir).resolve()
    audit = audit_draft(directory)
    if not audit["passed"]:
        return {"status": "invalid_sources", "audit": audit}
    latexmk, pdflatex = shutil.which("latexmk"), shutil.which("pdflatex")
    if latexmk:
        commands = [
            [
                latexmk,
                "-norc",
                "-pdf",
                "-interaction=nonstopmode",
                "-halt-on-error",
                "-no-shell-escape",
                "main.tex",
            ]
        ]
    elif pdflatex:
        commands = [[pdflatex, "-interaction=nonstopmode", "-halt-on-error", "-no-shell-escape", "main.tex"]]
        if read_json(directory / "claims.json")["reference_sources"]:
            bibtex = shutil.which("bibtex")
            if not bibtex:
                return {
                    "status": "unavailable",
                    "reason": "bibtex is required to compile references",
                    "audit": audit,
                }
            commands.append([bibtex, "main"])
        commands += [commands[0], commands[0]]
    else:
        return {
            "status": "unavailable",
            "reason": "Install a local TeX distribution providing latexmk or pdflatex",
            "audit": audit,
        }
    with (directory / "compile.log").open("w") as log:
        for command in commands:
            try:
                result = subprocess.run(
                    command,
                    cwd=directory,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    timeout=180,
                    env={
                        key: value
                        for key, value in dict(os.environ, openin_any="p", openout_any="p").items()
                        if not re.search(r"(?i)(key|token|secret|password|credential)", key)
                    },
                )
            except subprocess.TimeoutExpired:
                return {"status": "timeout", "log": str(directory / "compile.log")}
            if result.returncode:
                return {
                    "status": "failed",
                    "log": str(directory / "compile.log"),
                    "returncode": result.returncode,
                }
    pdf = directory / "main.pdf"
    manifest = read_json(directory / "claims.json")
    page_count = None
    pdfinfo = shutil.which("pdfinfo")
    if pdf.is_file() and pdfinfo:
        info = subprocess.run([pdfinfo, str(pdf)], capture_output=True, text=True, timeout=20)
        match = re.search(r"^Pages:\s+(\d+)", info.stdout, re.MULTILINE)
        page_count = int(match.group(1)) if match else None
    if page_count is not None:
        audit["page_limit_checked"] = True
        limit = manifest.get("page_limit")
        if limit and page_count > limit:
            audit["errors"].append(f"PDF has {page_count} pages; configured limit is {limit}")
            audit["passed"] = False
    return {
        "status": "compiled" if pdf.is_file() else "failed",
        "pdf": str(pdf),
        "log": str(directory / "compile.log"),
        "pages": page_count,
        "audit": audit,
    }
