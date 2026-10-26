import datetime
import json
import structlog
from typing import List, Optional
import numpy as np
from sqlalchemy import text
from sqlmodel import Session, select

from receipt_api.llm.embeddings import compute_embeddings_sync
from receipt_api.models import Constraint, ConstraintEmbedding, ConstraintEvidence, Edge
from receipt_api.schemas import (
    ConstraintCheckSpec,
    ConstraintScope,
    ConstraintSchema,
    EvidenceItem,
)

logger = structlog.get_logger(__name__)


def save_constraint(
    constraint: ConstraintSchema,
    repo_id: str,
    session: Session,
    embedding_vector: Optional[List[float]] = None,
) -> Constraint:
    """Save or update a constraint, its evidence items, FTS5 index, and embedding."""
    # 1. Update or create Constraint model
    db_c = session.exec(select(Constraint).where(Constraint.id == constraint.id)).first()
    if not db_c:
        db_c = Constraint(
            id=constraint.id,
            repo_id=repo_id,
            title=constraint.title,
            rule=constraint.rule,
            why=constraint.why,
            scope_json=constraint.scope.model_dump_json(),
            severity=constraint.severity,
            check_json=constraint.check.model_dump_json(),
            confidence=constraint.confidence,
            status=constraint.status,
            version=constraint.version,
            supersedes_json=json.dumps(constraint.supersedes),
            prevented_count=constraint.prevented_count,
        )
        session.add(db_c)
    else:
        db_c.title = constraint.title
        db_c.rule = constraint.rule
        db_c.why = constraint.why
        db_c.scope_json = constraint.scope.model_dump_json()
        db_c.severity = constraint.severity
        db_c.check_json = constraint.check.model_dump_json()
        db_c.confidence = constraint.confidence
        db_c.status = constraint.status
        db_c.version = constraint.version
        db_c.supersedes_json = json.dumps(constraint.supersedes)
        db_c.prevented_count = constraint.prevented_count
        db_c.last_confirmed_at = datetime.datetime.now(datetime.timezone.utc)

    # 2. Save Evidence
    # Remove existing evidence for this constraint to avoid duplicates
    existing_evidence = session.exec(
        select(ConstraintEvidence).where(ConstraintEvidence.constraint_id == constraint.id)
    ).all()
    for ev in existing_evidence:
        session.delete(ev)

    for idx, item in enumerate(constraint.evidence, start=1):
        ev_id = f"ev_{constraint.id}_{idx}"
        at_dt = None
        if item.at:
            try:
                at_dt = datetime.datetime.fromisoformat(item.at.replace("Z", "+00:00"))
            except Exception:
                at_dt = datetime.datetime.now(datetime.timezone.utc)

        db_ev = ConstraintEvidence(
            id=ev_id,
            constraint_id=constraint.id,
            type=item.type,
            url=item.url,
            sha=item.sha,
            excerpt=item.excerpt,
            at=at_dt,
        )
        session.add(db_ev)

    # 3. Update FTS5 Table
    try:
        session.exec(text("DELETE FROM constraints_fts WHERE id = :id"), params={"id": constraint.id})
        session.exec(
            text("INSERT INTO constraints_fts(id, title, rule, why) VALUES (:id, :title, :rule, :why)"),
            params={
                "id": constraint.id,
                "title": constraint.title,
                "rule": constraint.rule,
                "why": constraint.why,
            },
        )
    except Exception as e:
        logger.warning("FTS5 update warning", error=str(e))

    # 4. Save Vector Embedding
    if embedding_vector is None:
        text_to_embed = f"{constraint.title} {constraint.rule} {constraint.why}"
        embeddings = compute_embeddings_sync([text_to_embed])
        if embeddings:
            embedding_vector = embeddings[0]

    if embedding_vector:
        blob = np.array(embedding_vector, dtype=np.float32).tobytes()
        db_emb = session.exec(
            select(ConstraintEmbedding).where(ConstraintEmbedding.constraint_id == constraint.id)
        ).first()
        if not db_emb:
            db_emb = ConstraintEmbedding(constraint_id=constraint.id, vector=blob)
            session.add(db_emb)
        else:
            db_emb.vector = blob

    # 5. Save Edges (for Knowledge Graph)
    # Edge to scoped paths
    for p in constraint.scope.paths:
        session.add(
            Edge(
                src_type="constraint",
                src_id=constraint.id,
                dst_type="file",
                dst_id=p,
                kind="scopes_file",
                weight=1.0,
            )
        )
    # Edge to evidence URLs / PRs
    for ev in constraint.evidence:
        session.add(
            Edge(
                src_type="constraint",
                src_id=constraint.id,
                dst_type="evidence",
                dst_id=ev.url,
                kind=f"extracted_from_{ev.type}",
                weight=1.0,
            )
        )

    session.commit()
    session.refresh(db_c)
    return db_c


def get_constraint(constraint_id: str, session: Session) -> Optional[ConstraintSchema]:
    """Retrieve a single constraint by ID as ConstraintSchema."""
    db_c = session.exec(select(Constraint).where(Constraint.id == constraint_id)).first()
    if not db_c:
        return None

    db_evs = session.exec(
        select(ConstraintEvidence).where(ConstraintEvidence.constraint_id == constraint_id)
    ).all()

    evidence_items = [
        EvidenceItem(
            type=ev.type,  # type: ignore
            url=ev.url,
            sha=ev.sha,
            excerpt=ev.excerpt,
            at=ev.at.isoformat() if ev.at else None,
        )
        for ev in db_evs
    ]

    scope_dict = json.loads(db_c.scope_json) if db_c.scope_json else {}
    check_dict = json.loads(db_c.check_json) if db_c.check_json else {}
    supersedes_list = json.loads(db_c.supersedes_json) if db_c.supersedes_json else []

    return ConstraintSchema(
        id=db_c.id,
        title=db_c.title,
        rule=db_c.rule,
        why=db_c.why,
        scope=ConstraintScope(**scope_dict),
        severity=db_c.severity,  # type: ignore
        check=ConstraintCheckSpec(**check_dict),
        confidence=db_c.confidence,
        status=db_c.status,  # type: ignore
        evidence=evidence_items,
        prevented_count=db_c.prevented_count,
        version=db_c.version,
        supersedes=supersedes_list,
    )


def list_constraints(
    repo_id: str,
    session: Session,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    path: Optional[str] = None,
) -> List[ConstraintSchema]:
    """List constraints for a repository with optional filtering."""
    query = select(Constraint).where(Constraint.repo_id == repo_id)
    if status:
        query = query.where(Constraint.status == status)
    if severity:
        query = query.where(Constraint.severity == severity)

    db_constraints = session.exec(query).all()
    results: List[ConstraintSchema] = []

    for db_c in db_constraints:
        c_schema = get_constraint(db_c.id, session)
        if c_schema:
            if path:
                # Check if path matches any scoped path or prefix
                matches = False
                for p in c_schema.scope.paths:
                    clean_p = p.replace("**", "").replace("*", "")
                    if clean_p in path or path in clean_p:
                        matches = True
                        break
                if not matches:
                    continue
            results.append(c_schema)

    return results
