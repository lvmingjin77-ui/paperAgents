"""Evidence-bound LaTeX manuscripts: numbers come from recorded evidence, sections bind claim versions."""

from __future__ import annotations

import json
import math
from pathlib import Path
import re
import shutil
import subprocess

from .storage import digest, read_json, write_json

_CITE = re.compile(r"\\cite\w*\*?(?:\[[^]]*\])*\{([^}]+)\}")
_METRIC = re.compile(r"\\metric\{([^}]+)\}\{([^}]+)\}")


def _tex(text: object) -> str:
    table = {"\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
             "_": r"\_", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
    return "".join(table.get(c, c) for c in str(text))


def metric_catalog(state: dict) -> list[dict]:
    """Citable numbers: single runs and unit-bootstrap summaries of comparisons.

    ``\\metric{run}{metric}`` is one execution; ``\\metric{comparison}{baseline.metric.series.est|lo|hi}``
    is an estimate or interval bound of baseline, candidate or improvement over independent units.
    """
    catalog = []
    for run_id, run in state["runs"].items():
        if run["outcome"] == "completed":
            for name, value in run["metrics"].items():
                catalog.append(dict(run_id=run_id, metric=name, value=value, claim_ref=run["claim_ref"],
                                    split=run["split"], seed=run["seed"]))
    for eid, evidence in state["evidence"].items():
        if evidence["kind"] != "comparison":
            continue
        for baseline, report in evidence["content"]["baselines"].items():
            for metric, rows in report["unit_bootstrap"].items():
                for series in ("baseline", "candidate", "improvement"):
                    estimate, interval = rows[series]
                    for stat, value in zip(("est", "lo", "hi"), [estimate, *(interval or [None, None])]):
                        if value is not None:
                            catalog.append(dict(run_id=eid, metric=f"{baseline}.{metric}.{series}.{stat}",
                                                value=value, claim_ref=evidence["claim_ref"],
                                                split=evidence["content"]["split"], n_units=rows["n_units"]))
    for item in catalog:
        item["macro"] = f"\\metric{{{item['run_id']}}}{{{item['metric']}}}"
    return catalog


def generate_figures(run_dir: Path, state: dict) -> list[dict]:
    """One figure per comparison: estimates and unit-bootstrap intervals of candidate and baselines."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    directory = Path(run_dir) / "paper" / "figures"
    directory.mkdir(parents=True, exist_ok=True)
    figures = []
    for eid, evidence in sorted(state["evidence"].items()):
        content = evidence["content"]
        if evidence["kind"] != "comparison" or not any(r["unit_bootstrap"] for r in content["baselines"].values()):
            continue
        path = directory / f"{eid}.pdf"
        if not path.exists():
            metrics = sorted({m for r in content["baselines"].values() for m in r["unit_bootstrap"]})
            fig = Figure(figsize=(4 * len(metrics), 2.6), layout="constrained")
            FigureCanvasAgg(fig)
            for ax, metric in zip(fig.subplots(1, len(metrics), squeeze=False)[0], metrics):
                reports = {n: r["unit_bootstrap"][metric] for n, r in content["baselines"].items() if metric in r["unit_bootstrap"]}
                rows = [("candidate", next(iter(reports.values()))["candidate"])]
                rows += [(name, r["baseline"]) for name, r in reports.items()]
                for y, (label, (estimate, interval)) in enumerate(rows):
                    err = [[estimate - interval[0]], [interval[1] - estimate]] if interval else None
                    ax.errorbar([estimate], [y], xerr=err, fmt="o", color="#216653" if y == 0 else "#6b7280")
                ax.set_yticks(range(len(rows)), labels=[r[0] for r in rows])
                ax.set_xlabel(metric)
            fig.savefig(path, metadata={"CreationDate": None})
        units = next(r for r in content["baselines"].values() if r["unit_bootstrap"])["unit_bootstrap"]
        figures.append({
            "path": str(path), "claim_refs": [evidence["claim_ref"]], "evidence_id": eid,
            "caption": f"{content['split']} split, {content['purpose']} experiment: estimates with 95% intervals "
            f"from paired resampling of {next(iter(units.values()))['n_units']} independent units; a point without "
            "an interval could not be bounded by resampling.",
        })
    return figures


def _reference_source(reference: dict, papers: list[dict]) -> dict:
    """Bibliographic fields are copied from the corpus, never taken from the writer."""
    for paper in papers:
        if any(reference.get(k) and reference[k] == paper.get(k) for k in ("paper_id", "doi", "url")):
            return paper
    raise ValueError(f"Reference has no corpus source: {reference['key']}")


def freeze_snapshot(state: dict, claim_refs: list[str]) -> dict:
    claims = {ref: state["claims"][ref] for ref in claim_refs}
    snapshot = {
        "claims": claims,
        "claim_refs": list(claim_refs),
        "protocol": state["protocol"],
        "runs": {k: r for k, r in state["runs"].items() if r["claim_ref"] in claims and r["split"] != "test"},
        "evidence": {k: e for k, e in state["evidence"].items() if e["claim_ref"] in claims},
    }
    return json.loads(json.dumps(dict(snapshot, hash=digest(snapshot))))


def update_outline(run_dir: Path, state: dict) -> None:
    """W0/W1: a working index of claims, their evidence and citable development numbers."""
    lines = ["# 论文工作提纲", "", "随研究状态更新；尚未验证的主张不是论文结论。", "", "## 主张与证据", ""]
    for ref, claim in state["claims"].items():
        if claim["active"]:
            lines += [f"### {ref}（{claim['kind']}）", "", claim["text"], "",
                      f"- 结论：{claim['verdict']}；进度：{claim['stage']}；作者：{claim['owner']}",
                      "- 证据：" + (", ".join(f"`{e}`" for e in claim["evidence_ids"]) or "尚无"), ""]
    lines += ["## 开发集数字", ""]
    lines += [f"- `{m['macro']}` = {m['value']:.6g}（{m['claim_ref'] or 'baseline'}）"
              for m in metric_catalog(state) if m["split"] != "test"]
    path = Path(run_dir) / "paper" / "outline.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


def materialize_draft(run_dir: Path, state: dict, content: dict, config: dict) -> dict:
    """Write a versioned manuscript. Raises when a section, number, citation or figure is unbound."""
    papers = state["knowledge"].get("corpus", {}).get("papers", [])
    references = {ref["key"]: _reference_source(ref, papers) for ref in content["references"]}
    numbers = {(m["run_id"], m["metric"]): m for m in metric_catalog(state)}
    catalog = {f["path"]: f for f in generate_figures(run_dir, state)}
    files = {}
    for index, section in enumerate(content["sections"]):
        refs, tex = section["claim_refs"], section["tex"]
        if not refs or not set(refs) <= set(state["claims"]):
            raise ValueError(f"Section {index} must bind existing claim versions")
        for group in _CITE.findall(tex):
            if not set(group.split(",")) <= set(references):
                raise ValueError(f"Unknown citation: {group}")
        for source, metric in _METRIC.findall(tex):
            number = numbers.get((source, metric))
            if number is None or (number["claim_ref"] and number["claim_ref"] not in refs):
                raise ValueError(f"Result {source}/{metric} is unknown or belongs to an unbound claim version")
        files[f"sections/{index:02d}.tex"] = f"% claim_refs: {', '.join(refs)}\n\\section{{{_tex(section['name'])}}}\n{tex}\n"
    for figure in content.get("figures", []):
        source = catalog.get(figure["path"])
        if source is None or set(figure["claim_refs"]) != set(source["claim_refs"]):
            raise ValueError("Figures must come from this run's figure catalog with their claim bindings")
        files[f"sections/{len(files):02d}.tex"] = (
            f"% claim_refs: {', '.join(source['claim_refs'])}\n\\begin{{figure}}[htbp]\\centering\n"
            f"\\includegraphics[width=\\linewidth]{{figures/{Path(source['path']).name}}}\n"
            f"\\caption{{{_tex(figure.get('caption') or source['caption'])}}}\\end{{figure}}\n"
        )
    files["metrics.tex"] = "\\newcommand{\\metric}[2]{\\csname metric:#1:#2\\endcsname}\n" + "".join(
        f"\\expandafter\\def\\csname metric:{s}:{m}\\endcsname{{{n['value']:.4g}}}\n" for (s, m), n in numbers.items()
        if isinstance(n["value"], (int, float)) and math.isfinite(n["value"])
    )
    files["references.bib"] = "\n\n".join(
        f"@misc{{{key},\n" + ",\n".join(f"  {f} = {{{_tex(paper[f])}}}" for f in ("title", "year", "doi", "url")
                                         if paper.get(f)) + "\n}" for key, paper in references.items()
    ) + "\n"
    output = config["output"]
    author = "Anonymous Authors" if output["anonymous"] else output.get("authors", "PaperAgents Authors")
    body = "".join(f"\\input{{{name}}}\n" for name in files if name.startswith("sections/"))
    header = ("\\documentclass[11pt]{article}\n\\usepackage{amsmath,graphicx,booktabs,url}\n"
              "\\title{%%PAPERAGENTS_TITLE%%}\n\\author{%%PAPERAGENTS_AUTHORS%%}\n\\begin{document}\n\\maketitle\n")
    footer = "\\bibliographystyle{plain}\n\\bibliography{references}\n\\end{document}\n"
    template = Path(output["template"]).expanduser() if output["template"] != "article" else None
    if template:
        template = template if template.is_absolute() else Path(run_dir).parents[1] / template
        header = (template / "header.tex").read_text()
        footer = (template / "footer.tex").read_text() if (template / "footer.tex").exists() else footer
    header = header.replace("%%PAPERAGENTS_TITLE%%", _tex(content["title"])).replace("%%PAPERAGENTS_AUTHORS%%", _tex(author))
    files["main.tex"] = header.replace("\\begin{document}", "\\input{metrics.tex}\n\\begin{document}", 1) + body + footer
    version = digest(files)[:20]
    directory = Path(run_dir) / "paper" / version
    for name, text in files.items():
        (directory / name).parent.mkdir(parents=True, exist_ok=True)
        (directory / name).write_text(text)
    (directory / "figures").mkdir(exist_ok=True)
    for figure in content.get("figures", []):
        shutil.copy2(figure["path"], directory / "figures")
    if template:
        for path in template.iterdir():
            if path.suffix in {".sty", ".cls", ".bst"}:
                shutil.copy2(path, directory)
    result = {"path": str(directory), "main": str(directory / "main.tex"), "version": version, "title": content["title"]}
    write_json(Path(run_dir) / "paper" / "latest.json", result)
    return result


def compile_draft(directory: Path, output: dict) -> dict:
    """Compile with shell escape disabled and check the configured page limit."""
    directory = Path(directory)
    if shutil.which("latexmk"):
        commands = [["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error", "-no-shell-escape", "main.tex"]]
    elif shutil.which("pdflatex") and shutil.which("bibtex"):
        tex = ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "-no-shell-escape", "main.tex"]
        commands = [tex, ["bibtex", "main"], tex, tex]
    else:
        return {"status": "unavailable", "reason": "Install a TeX distribution providing latexmk or pdflatex and bibtex"}
    with (directory / "compile.log").open("w") as log:
        for command in commands:
            if subprocess.run(command, cwd=directory, stdout=log, stderr=subprocess.STDOUT, timeout=300).returncode:
                return {"status": "failed", "log": str(directory / "compile.log")}
    pdf, pages = directory / "main.pdf", None
    if shutil.which("pdfinfo"):
        info = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
        pages = int(re.search(r"^Pages:\s+(\d+)", info, re.M).group(1))
    if pages and pages > output["page_limit"]:
        return {"status": "over_page_limit", "pages": pages, "pdf": str(pdf)}
    return {"status": "compiled", "pdf": str(pdf), "pages": pages}
