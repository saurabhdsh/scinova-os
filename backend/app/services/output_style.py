"""Shared professional output styling for all agent LLM prompts and post-processing."""

from __future__ import annotations

import re

OUTPUT_STYLE_RULES = """
Presentation rules (strict — follow for every text field):
- Write like a senior pharma R&D consultant: polished, confident, decision-ready prose.
- NEVER use markdown: no # headings, no ** bold, no backtick code fences, no markdown bullet syntax (- or *).
- Use complete sentences and short paragraphs in "answer" and "summary" fields.
- Put bullet-style content in dedicated JSON arrays (findings, key_findings, hypotheses, evidence_for, etc.).
- Inline citations only as [1], [2], [Doc-N], or [PubMed-N] — no URLs in the narrative unless required.
- Avoid filler phrases ("In conclusion", "It is important to note"). Be direct and evidence-led.
"""

PROSE_KEYS = frozenset({
    "answer", "summary", "narrative", "executive_summary", "report_body",
    "hypothesis_statement", "recommendation",
})

LIST_KEYS = frozenset({
    "findings", "key_findings", "gaps", "evidence_gaps", "patents_or_ip",
    "conflicting_evidence", "recommended_next_sources", "knowledge_gaps",
    "suggested_graph_queries", "evidence_for", "evidence_against",
    "section_names", "risks", "decisions_needed", "agenda",
})


def augment_system_prompt(system: str) -> str:
    if OUTPUT_STYLE_RULES.strip() in system:
        return system
    return f"{system.rstrip()}\n\n{OUTPUT_STYLE_RULES}"


def polish_prose(text: str) -> str:
    if not text:
        return ""
    cleaned: list[str] = []
    in_fence = False
    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            cleaned.append(stripped)
            continue
        header = re.match(r"^#{1,6}\s+(.+)$", stripped)
        if header:
            cleaned.append(header.group(1).strip())
            continue
        stripped = re.sub(r"\*\*([^*]+)\*\*", r"\1", stripped)
        stripped = re.sub(r"\*([^*]+)\*", r"\1", stripped)
        stripped = re.sub(r"`([^`]+)`", r"\1", stripped)
        bullet = re.match(r"^[-*+]\s+(.+)$", stripped)
        if bullet:
            cleaned.append(f"• {bullet.group(1).strip()}")
            continue
        if stripped:
            cleaned.append(stripped)
    result = "\n".join(cleaned)
    return re.sub(r"\n{3,}", "\n\n", result).strip()


def polish_agent_output(output: dict | None) -> dict:
    if not output:
        return {}
    polished = dict(output)
    for key, value in list(polished.items()):
        if key in PROSE_KEYS and isinstance(value, str):
            polished[key] = polish_prose(value)
        elif key in LIST_KEYS and isinstance(value, list):
            polished[key] = [
                polish_prose(str(item)) if isinstance(item, str) else item
                for item in value
            ]
        elif key == "hypotheses" and isinstance(value, list):
            polished[key] = [
                {
                    **h,
                    **{k: polish_prose(v) if isinstance(v, str) and k in PROSE_KEYS else v
                       for k, v in h.items()},
                }
                if isinstance(h, dict) else h
                for h in value
            ]
    if isinstance(polished.get("summary"), str):
        polished["summary"] = polish_prose(polished["summary"])
    if isinstance(polished.get("answer"), str):
        polished["answer"] = polish_prose(polished["answer"])
    return polished
