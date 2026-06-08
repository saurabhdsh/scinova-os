"""Build detailed scientific report sections from agent outputs for storage and export."""

from __future__ import annotations


def _hypothesis_block(h: dict, index: int) -> str:
    lines = [
        f"{index}. {h.get('title') or h.get('hypothesis') or f'Hypothesis {index}'}",
        "",
        f"Statement: {h.get('statement', '—')}",
    ]
    if h.get("target_or_mechanism"):
        lines.append(f"Target / mechanism: {h['target_or_mechanism']}")
    if h.get("disease_context"):
        lines.append(f"Disease context: {h['disease_context']}")
    if h.get("rationale"):
        lines.append("")
        lines.append(f"Rationale: {h['rationale']}")
    if h.get("evidence_strength"):
        lines.append(f"Evidence strength: {h['evidence_strength']}")
    if h.get("confidence") is not None:
        lines.append(f"Confidence score: {h['confidence']}")
    if h.get("suggested_experiments"):
        lines.append("")
        lines.append("Suggested validation experiments:")
        for exp in h["suggested_experiments"]:
            lines.append(f"  • {exp}")
    return "\n".join(lines)


def _experiment_plan_block(ep: dict) -> str:
    if not isinstance(ep, dict):
        return str(ep)
    lines = []
    for label, key in [
        ("Objective", "objective"),
        ("Study type", "study_type"),
        ("Model system", "model_system"),
        ("Sample size rationale", "sample_size_rationale"),
        ("Duration (weeks)", "duration_weeks"),
    ]:
        if ep.get(key) not in (None, ""):
            lines.append(f"{label}: {ep[key]}")
    for label, key in [
        ("Primary endpoints", "primary_endpoints"),
        ("Secondary endpoints", "secondary_endpoints"),
        ("Controls", "controls"),
        ("Materials", "materials"),
        ("Success criteria", "success_criteria"),
        ("Risks", "risks"),
    ]:
        items = ep.get(key)
        if items:
            lines.append(f"\n{label}:")
            for item in items:
                lines.append(f"  • {item}")
    timeline = ep.get("timeline")
    if timeline:
        lines.append("\nTimeline:")
        for phase in timeline:
            if isinstance(phase, dict):
                lines.append(
                    f"  • {phase.get('phase', 'Phase')}: {phase.get('duration', '')} — "
                    f"{', '.join(phase.get('activities') or [])}"
                )
            else:
                lines.append(f"  • {phase}")
    return "\n".join(lines) if lines else "See narrative sections for experiment design details."


def _doe_block(doe: dict) -> str:
    if not isinstance(doe, dict):
        return str(doe)
    lines = [f"Design type: {doe.get('design_type', '—')}"]
    if doe.get("statistical_plan"):
        lines.append(f"Statistical plan: {doe['statistical_plan']}")
    if doe.get("power_analysis"):
        lines.append(f"Power analysis: {doe['power_analysis']}")
    factors = doe.get("factors") or []
    if factors:
        lines.append("\nFactors:")
        for f in factors:
            if isinstance(f, dict):
                lines.append(f"  • {f.get('name')}: levels {f.get('levels')} ({f.get('type', '')})")
    runs = doe.get("runs") or []
    if runs:
        lines.append(f"\nPlanned runs: {len(runs)}")
        for run in runs[:12]:
            if isinstance(run, dict):
                lines.append(f"  • Run {run.get('run_id', '?')}: {run.get('factor_settings', run)}")
    responses = doe.get("response_variables") or []
    if responses:
        lines.append("\nResponse variables: " + ", ".join(str(r) for r in responses))
    return "\n".join(lines)


def _list_block(title: str, items: list) -> str:
    if not items:
        return ""
    return "\n".join([title, *[f"• {x}" for x in items]])


def enrich_report_content(
    report_type: str,
    output: dict,
    *,
    query: str = "",
    citations: list | None = None,
) -> dict:
    """Expand agent output into detailed body + section_content for UI and exports."""
    output = dict(output or {})
    citations = citations or []

    summary = output.get("summary") or ""
    answer = output.get("answer") or summary or ""
    sections: list[dict] = []

    existing = output.get("sections") or []
    if existing and all(isinstance(s, dict) and (s.get("content") or "").strip() for s in existing):
        section_content = existing
    else:
        if summary:
            sections.append({
                "name": "Executive Summary",
                "content": summary,
            })

        if answer and answer != summary:
            sections.append({
                "name": "Analysis & Narrative",
                "content": answer,
            })

        if report_type in ("hypothesis_report", "target_discovery") and output.get("hypotheses"):
            hyp_text = "\n\n".join(
                _hypothesis_block(h, i + 1)
                for i, h in enumerate(output["hypotheses"])
                if isinstance(h, dict)
            )
            sections.append({"name": "Ranked Hypotheses", "content": hyp_text})

        if output.get("verdict"):
            verdict_text = f"Overall verdict: {str(output['verdict']).replace('_', ' ').title()}"
            if output.get("hypothesis_statement"):
                verdict_text = f"Hypothesis: {output['hypothesis_statement']}\n\n{verdict_text}"
            sections.append({"name": "Validation Verdict", "content": verdict_text})

        if output.get("evidence_for"):
            sections.append({
                "name": "Evidence Supporting Conclusions",
                "content": _list_block("", output["evidence_for"]).strip(),
            })
        if output.get("evidence_against"):
            sections.append({
                "name": "Evidence Against / Conflicting Data",
                "content": _list_block("", output["evidence_against"]).strip(),
            })

        if output.get("gaps"):
            sections.append({
                "name": "Knowledge Gaps",
                "content": _list_block("", output["gaps"]).strip(),
            })

        if output.get("experiment_plan"):
            sections.append({
                "name": "Experiment Plan",
                "content": _experiment_plan_block(output["experiment_plan"]),
            })

        if output.get("doe_design"):
            sections.append({
                "name": "Design of Experiments (DOE)",
                "content": _doe_block(output["doe_design"]),
            })

        if output.get("findings") and report_type not in ("hypothesis_report",):
            sections.append({
                "name": "Key Findings",
                "content": _list_block("", output["findings"]).strip(),
            })

        if output.get("limitations"):
            sections.append({
                "name": "Limitations",
                "content": _list_block("", output["limitations"]).strip(),
            })

        if output.get("recommendations"):
            sections.append({
                "name": "Recommendations & Next Steps",
                "content": _list_block("", output["recommendations"]).strip(),
            })

        figures = output.get("figures") or output.get("figures_list") or []
        if figures:
            fig_lines = []
            for i, fig in enumerate(figures, 1):
                fig_lines.append(f"Figure {i}: {fig}" if isinstance(fig, str) else f"Figure {i}: {fig}")
            sections.append({"name": "Suggested Figures & Visualizations", "content": "\n".join(fig_lines)})

        if query:
            sections.insert(0, {
                "name": "Research Scope",
                "content": f"Report request:\n{query}",
            })

        if citations:
            cite_lines = []
            for cite in citations:
                idx = cite.get("index", "?")
                title = cite.get("title", "Source")
                source = cite.get("source", "")
                excerpt = (cite.get("excerpt") or "")[:350]
                line = f"[{idx}] {title} ({source})"
                if excerpt:
                    line += f"\n    Excerpt: {excerpt}"
                if cite.get("url"):
                    line += f"\n    URL: {cite['url']}"
                cite_lines.append(line)
            sections.append({
                "name": "References & Evidence Trail",
                "content": "\n\n".join(cite_lines),
            })

        section_content = sections

    full_body = "\n\n".join(
        f"## {s['name']}\n\n{s['content']}"
        for s in section_content
        if isinstance(s, dict) and s.get("content")
    )
    if not full_body:
        full_body = answer or summary

    word_count = len(full_body.split()) if full_body else output.get("word_count", 0)

    return {
        **output,
        "summary": summary,
        "answer": answer,
        "body": full_body,
        "sections": [s.get("name") for s in section_content if isinstance(s, dict)],
        "section_content": section_content,
        "word_count": word_count,
    }
