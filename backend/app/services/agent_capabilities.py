"""Agent capability detection for specialized pipelines."""

HYPOTHESIS_AGENTS = (
    "hypothesis builder",
    "hypothesis validation",
    "target hypothesis",
    "hypothesis generation",
)

EXPERIMENT_AGENTS = (
    "experiment planner",
    "doe designer",
    "assay design",
    "in-vivo study design",
    "study design agent",
)

REPORT_AGENTS = (
    "study report generator",
    "scientific writer",
    "result capture",
)

LITERATURE_AGENTS = (
    "literature/patent miner",
    "literature miner",
    "patent miner",
    "evidence scout",
    "paper summarizer",
    "knowledge scout",
)

TARGET_DISCOVERY_AGENTS = (
    "pathway insight",
    "target validation",
    "biomarker discovery",
    "druggability finder",
    "druggability",
)

KNOWLEDGE_GRAPH_AGENTS = (
    "ontology mapper",
    "kg builder",
)


MOLECULAR_AGENTS = (
    "admet",
    "virtual screening",
    "mpo scoring",
    "molecular property",
    "explainable admet",
)

SCREENING_AGENTS = (
    "virtual screening",
)


def _name_matches(agent, keywords: tuple[str, ...]) -> bool:
    name = (agent.name or "").lower()
    return any(k in name for k in keywords)


def is_hypothesis_agent(agent) -> bool:
    return _name_matches(agent, HYPOTHESIS_AGENTS)


def is_experiment_agent(agent) -> bool:
    return _name_matches(agent, EXPERIMENT_AGENTS)


def is_report_agent(agent) -> bool:
    return _name_matches(agent, REPORT_AGENTS)


def is_literature_agent(agent) -> bool:
    return _name_matches(agent, LITERATURE_AGENTS)


def is_target_discovery_agent(agent) -> bool:
    return _name_matches(agent, TARGET_DISCOVERY_AGENTS)


def is_knowledge_graph_agent(agent) -> bool:
    return _name_matches(agent, KNOWLEDGE_GRAPH_AGENTS)


def is_molecular_agent(agent) -> bool:
    return _name_matches(agent, MOLECULAR_AGENTS)


def is_screening_agent(agent) -> bool:
    return _name_matches(agent, SCREENING_AGENTS)


def get_specialized_task_type(agent) -> str | None:
    if is_hypothesis_agent(agent):
        return "hypothesis"
    if is_experiment_agent(agent):
        return "experiment"
    if is_report_agent(agent):
        return "report"
    if is_literature_agent(agent):
        return "literature"
    if is_target_discovery_agent(agent):
        return "target_discovery"
    if is_knowledge_graph_agent(agent):
        return "knowledge_graph"
    if is_molecular_agent(agent):
        return "molecular"
    return None


def is_qa_mode(input_data: dict) -> bool:
    task = str(input_data.get("task_type", "")).lower()
    return task in ("qa", "query", "question")


def agent_supports_specialized(agent, input_data: dict) -> bool:
    if is_qa_mode(input_data):
        return False
    task = get_specialized_task_type(agent)
    if not task:
        return False
    if task == "molecular":
        return bool(
            input_data.get("compound_list")
            or input_data.get("compounds")
            or input_data.get("smiles")
            or str(input_data.get("query", "")).strip()
        )
    return bool(str(input_data.get("query", "")).strip())
