import random
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.db_models import (
    Agent,
    ApprovalRequest,
    AuditEvent,
    DataSource,
    Document,
    GraphNode,
    GraphRelationship,
    IngestionJob,
    RiskAlert,
    SLMProfile,
    ScientificEntity,
    ScientificReport,
    User,
    WorkflowRun,
    WorkflowTemplate,
)
from app.seed_data import (
    AGENTS,
    DOCUMENT_TITLES,
    ENTITY_SAMPLES,
    RELATIONSHIP_TYPES,
    SLM_PROFILES,
    WORKFLOW_TEMPLATES,
)


SOURCE_TYPES = [
    "research_paper", "patent", "protocol", "study_report", "eln_export",
    "lims_export", "assay_dataset", "omics_dataset", "compound_library",
    "regulatory_document", "csv", "xlsx", "json", "txt", "docx", "pdf",
]

FILE_FORMATS = ["PDF", "CSV", "XLSX", "JSON", "TXT", "DOCX"]


def seed_database(db: Session) -> None:
    if db.query(Document).count() > 0:
        return

    # Users (dev/demo only — production users are created via CLI)
    admin = User(
        username="admin",
        password_hash=hash_password("admin123"),
        role="admin",
        full_name="Platform Administrator",
    )
    scientist = User(
        username="scientist",
        password_hash=hash_password("sci123"),
        role="scientist",
        full_name="Dr. Sarah Chen",
    )
    reviewer = User(
        username="reviewer",
        password_hash=hash_password("rev123"),
        role="reviewer",
        full_name="Dr. James Morrison",
    )
    db.add(admin)
    db.add(scientist)
    db.add(reviewer)
    db.flush()
    admin_id = admin.id

    # Data sources
    connectors = [
        ("PubMed Connector", "research_paper"),
        ("Patent Database", "patent"),
        ("ELN Integration", "eln_export"),
        ("LIMS Bridge", "lims_export"),
        ("Omics Pipeline", "omics_dataset"),
        ("Compound Registry", "compound_library"),
        ("Regulatory Archive", "regulatory_document"),
        ("Local File Upload", "file_upload"),
    ]
    for name, stype in connectors:
        db.add(DataSource(
            name=name,
            source_type=stype,
            connector_status="active",
            last_sync=datetime.utcnow() - timedelta(hours=random.randint(1, 72)),
            document_count=random.randint(5, 25),
        ))

    # Documents (50)
    docs = []
    for i in range(50):
        if i < len(DOCUMENT_TITLES):
            title, stype, fmt = DOCUMENT_TITLES[i]
        else:
            stype = random.choice(SOURCE_TYPES)
            fmt = random.choice(FILE_FORMATS)
            title = f"Document {i + 1}: {stype.replace('_', ' ').title()} - Batch {random.randint(100, 999)}"
        doc = Document(
            title=title,
            source_type=stype,
            file_format=fmt,
            file_path=f"/storage/uploads/doc_{i + 1}.{fmt.lower()}",
            status=random.choice(["indexed", "indexed", "indexed", "processing", "archived"]),
            metadata_json={
                "author": random.choice(["Dr. Chen", "Dr. Morrison", "Dr. Patel", "Dr. Kim"]),
                "pages": random.randint(5, 120),
                "chunks": random.randint(10, 80),
                "embeddings": random.randint(10, 80),
            },
            version=random.randint(1, 3),
            user_id=admin_id,
            created_at=datetime.utcnow() - timedelta(days=random.randint(1, 365)),
        )
        docs.append(doc)
        db.add(doc)
    db.flush()

    # Ingestion jobs for recent docs
    stages = ["upload", "extract", "chunk", "embed", "index", "entity_extract", "graph_update", "complete"]
    for doc in docs[:15]:
        completed = random.randint(4, 8)
        db.add(IngestionJob(
            document_id=doc.id,
            user_id=admin_id,
            status="completed" if completed >= 7 else "processing",
            stage=stages[min(completed, 7)],
            progress=min(completed / 7 * 100, 100),
            stages_completed=stages[:completed],
            created_at=doc.created_at,
            completed_at=doc.created_at + timedelta(minutes=random.randint(5, 45)) if completed >= 7 else None,
        ))

    # Scientific entities (100)
    entities = []
    for i in range(100):
        if i < len(ENTITY_SAMPLES):
            name, etype = ENTITY_SAMPLES[i]
        else:
            etype = random.choice([
                "Gene", "Protein", "Disease", "Target", "Biomarker", "Compound",
                "Pathway", "Assay", "ADMET attribute",
            ])
            name = f"{etype}-{random.randint(1000, 9999)}"
        entity = ScientificEntity(
            name=name,
            entity_type=etype,
            description=f"Scientific entity: {name} ({etype})",
            ontology_id=f"ONT:{random.randint(10000, 99999)}" if random.random() > 0.3 else None,
            source_document_id=random.choice(docs).id,
            confidence=round(random.uniform(0.7, 0.99), 2),
            metadata_json={"extracted_by": "Entity Resolver Agent", "version": 1},
        )
        entities.append(entity)
        db.add(entity)
    db.flush()

    # Graph nodes from entities
    nodes = []
    for entity in entities[:60]:
        node = GraphNode(
            label=entity.name,
            node_type=entity.entity_type,
            entity_id=entity.id,
            properties_json={"confidence": entity.confidence},
            evidence_json=[{
                "source": f"doc_{random.randint(1, 50)}",
                "text": f"Evidence supporting {entity.name}",
                "confidence": entity.confidence,
            }],
        )
        nodes.append(node)
        db.add(node)
    db.flush()

    # Graph relationships (80)
    rel_count = 0
    for _ in range(80):
        if len(nodes) < 2:
            break
        src, tgt = random.sample(nodes, 2)
        rel_type_info = random.choice(RELATIONSHIP_TYPES)
        db.add(GraphRelationship(
            source_node_id=src.id,
            target_node_id=tgt.id,
            relationship_type=rel_type_info[1],
            properties_json={"weight": round(random.uniform(0.5, 1.0), 2)},
            evidence_json=[{
                "source_document": random.choice(docs).title,
                "excerpt": f"{src.label} {rel_type_info[1]} {tgt.label}",
            }],
            confidence=round(random.uniform(0.65, 0.95), 2),
        ))
        rel_count += 1

    # Agents
    for agent_data in AGENTS:
        db.add(Agent(**agent_data, status="ready"))

    # SLM profiles
    for slm in SLM_PROFILES:
        db.add(SLMProfile(**slm))

    # Workflow templates
    templates = []
    for wf in WORKFLOW_TEMPLATES:
        t = WorkflowTemplate(**wf)
        templates.append(t)
        db.add(t)
    db.flush()

    # Completed workflow runs
    for i, tmpl in enumerate(templates):
        steps = []
        for j, step in enumerate(tmpl.steps_json):
            steps.append({
                **step,
                "status": "completed" if j < len(tmpl.steps_json) - 1 else "completed",
                "output": f"Step {j + 1} output for {step['agent']}",
                "confidence": round(random.uniform(0.75, 0.95), 2),
            })
        db.add(WorkflowRun(
            template_id=tmpl.id,
            user_id=admin_id,
            name=f"{tmpl.name} Run #{i + 1}",
            status="completed",
            steps_json=steps,
            current_step=len(steps),
            confidence=round(random.uniform(0.8, 0.92), 2),
            output_json={"summary": f"Workflow {tmpl.name} completed successfully"},
            evidence_json=[{"source": "multiple", "count": random.randint(5, 20)}],
            created_at=datetime.utcnow() - timedelta(days=random.randint(1, 30)),
            completed_at=datetime.utcnow() - timedelta(days=random.randint(0, 29)),
        ))

    # Audit events (20)
    audit_actions = [
        ("agent_run", "Agent execution completed"),
        ("document_ingest", "Document ingested and indexed"),
        ("approval_granted", "Human approval granted"),
        ("model_routing", "Model routing decision logged"),
        ("workflow_complete", "Workflow execution completed"),
        ("entity_extracted", "Scientific entity extracted"),
        ("graph_updated", "Knowledge graph updated"),
        ("slm_inference", "SLM inference executed"),
        ("risk_detected", "Risk alert triggered"),
        ("report_generated", "Scientific report generated"),
    ]
    for i in range(20):
        action_type, action_desc = random.choice(audit_actions)
        db.add(AuditEvent(
            event_type=action_type,
            actor=random.choice(["admin", "scientist", "reviewer", "system"]),
            resource_type=random.choice(["agent", "document", "workflow", "model"]),
            resource_id=f"res_{random.randint(1000, 9999)}",
            action=action_desc,
            details_json={"timestamp": datetime.utcnow().isoformat(), "index": i},
            created_at=datetime.utcnow() - timedelta(hours=random.randint(1, 720)),
        ))

    # Risk alerts (10)
    risk_titles = [
        ("High-risk agent execution pending approval", "high", "agent_execution"),
        ("Potential IP conflict detected in compound SN-2847", "high", "ip_protection"),
        ("GxP compliance gap in study report SR-2025-12", "medium", "gxp_compliance"),
        ("PII detected in uploaded document batch 47", "high", "privacy"),
        ("Model drift detected in ADMET prediction model", "medium", "model_ops"),
        ("Off-target binding risk for lead compound LC-891", "medium", "safety"),
        ("Data lineage gap in omics dataset GSE198234", "low", "data_governance"),
        ("SLM accuracy below threshold for bioinformatics model", "medium", "model_ops"),
        ("Unapproved workflow step bypass attempt", "high", "governance"),
        ("Regulatory document version mismatch ICH M7", "medium", "regulatory"),
    ]
    for title, severity, category in risk_titles:
        db.add(RiskAlert(
            title=title,
            description=f"Automated detection: {title}",
            severity=severity,
            category=category,
            status=random.choice(["open", "open", "investigating", "resolved"]),
            source=random.choice(["Governance Engine", "Compliance Checker", "AI Risk Assessor"]),
            created_at=datetime.utcnow() - timedelta(days=random.randint(1, 14)),
        ))

    # Approval requests
    for i in range(5):
        db.add(ApprovalRequest(
            title=f"Approval required: Agent run #{1000 + i}",
            request_type="agent_execution",
            status=random.choice(["pending", "approved", "rejected"]),
            requested_by=random.choice(["scientist", "admin"]),
            details_json={"agent": random.choice(AGENTS)["name"], "risk_level": "high"},
            created_at=datetime.utcnow() - timedelta(days=random.randint(1, 7)),
        ))

    # Scientific reports (10)
    report_types = [
        ("Hypothesis Report: JAK1 in RA", "hypothesis_report"),
        ("Target Discovery Summary: EGFR Pathway", "target_discovery"),
        ("Experiment Plan: PK Study PR-2025-041", "experiment_plan"),
        ("Study Report: 28-day Tox SN-1923", "study_report"),
        ("CMC Readiness Assessment SN-2847", "cmc_readiness"),
        ("Competitive Landscape: Kinase Inhibitors", "competitive_intel"),
        ("ADMET Profile Report Batch 47", "admet_report"),
        ("Biomarker Discovery: NSCLC Panel", "biomarker_report"),
        ("GxP Compliance Audit Q4 2025", "compliance_report"),
        ("Literature Review: PD-1/PD-L1 Inhibitors", "literature_review"),
    ]
    for title, rtype in report_types:
        db.add(ScientificReport(
            title=title,
            report_type=rtype,
            user_id=admin_id,
            content_json={
                "sections": ["Executive Summary", "Methods", "Results", "Discussion", "References"],
                "word_count": random.randint(2000, 8000),
                "figures": random.randint(3, 12),
                "citations": random.randint(15, 60),
            },
            status=random.choice(["draft", "review", "approved", "published"]),
            created_at=datetime.utcnow() - timedelta(days=random.randint(1, 60)),
        ))

    db.commit()
