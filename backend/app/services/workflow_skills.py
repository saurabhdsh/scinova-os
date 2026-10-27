"""Skills a scientist can attach to one agent inside a custom pipeline."""

PIPELINE_SKILLS = (
    {
        "id": "cite-sources",
        "name": "Cite sources",
        "instruction": "Name the evidence behind each scientific claim.",
    },
    {
        "id": "stay-on-question",
        "name": "Stay on the question",
        "instruction": "Answer the research question directly and leave unrelated topics out.",
    },
    {
        "id": "flag-uncertainty",
        "name": "Flag uncertainty",
        "instruction": "State what is known, what is uncertain, and what evidence is missing.",
    },
    {
        "id": "compare-evidence",
        "name": "Compare evidence",
        "instruction": "Weigh supporting and contradicting evidence instead of listing only one side.",
    },
    {
        "id": "safety-lens",
        "name": "Safety lens",
        "instruction": "Call out safety and risk signals when the evidence supports them.",
    },
    {
        "id": "scientist-brief",
        "name": "Scientist brief",
        "instruction": "Write for a scientist: concise, specific, and free of promotional language.",
    },
)

SKILL_BY_ID = {skill["id"]: skill for skill in PIPELINE_SKILLS}
MAX_SKILLS_PER_AGENT = 4
MAX_CUSTOM_SKILL_LENGTH = 240


def resolve_skills(selections: list) -> list[dict]:
    """Keep known skills and one short custom skill. Ignore anything else."""
    resolved = []
    seen = set()
    custom_used = False
    for item in selections or []:
        skill_id = str(getattr(item, "id", "") or "").strip()
        if skill_id in seen or len(resolved) >= MAX_SKILLS_PER_AGENT:
            continue
        if skill_id == "custom":
            if custom_used:
                continue
            text = str(getattr(item, "instruction", "") or "").strip()
            if not text:
                continue
            custom_used = True
            seen.add(skill_id)
            resolved.append({
                "id": "custom",
                "name": "Custom skill",
                "instruction": text[:MAX_CUSTOM_SKILL_LENGTH],
            })
            continue
        known = SKILL_BY_ID.get(skill_id)
        if not known:
            continue
        seen.add(skill_id)
        resolved.append(dict(known))
    return resolved


def skill_instructions(skills: list) -> str:
    lines = []
    for skill in skills or []:
        name = str(skill.get("name") or "").strip()
        instruction = str(skill.get("instruction") or "").strip()
        if name and instruction:
            lines.append(f"- {name}: {instruction}")
    if not lines:
        return ""
    return "Apply these skills for this pipeline step:\n" + "\n".join(lines)
