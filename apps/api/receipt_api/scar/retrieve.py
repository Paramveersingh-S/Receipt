import json
import structlog
from typing import Dict, List, Optional, Tuple
import numpy as np
from sqlalchemy import text
from sqlmodel import Session, select

from receipt_api.llm.embeddings import compute_embeddings_sync, cosine_similarity
from receipt_api.models import Constraint, ConstraintEmbedding
from receipt_api.scar.store import get_constraint
from receipt_api.schemas import ConstraintSchema

logger = structlog.get_logger(__name__)


def _fts_search(repo_id: str, query: str, session: Session, limit: int = 20) -> List[Tuple[str, int]]:
    """Query SQLite FTS5 index and return list of (constraint_id, rank)."""
    # Clean query for FTS5 (escape special chars, retain alphanumerics and words)
    words = [w for w in query.replace('"', "").replace("'", "").replace("*", "").split() if len(w) > 1]
    if not words:
        return []

    # Build FTS match expression: "word1" OR "word2" OR ...
    fts_query = " OR ".join(f'"{w}"' for w in words)

    sql = """
        SELECT c.id, bm25(constraints_fts) as rank
        FROM constraints_fts f
        JOIN constraints c ON c.id = f.id
        WHERE c.repo_id = :repo_id
          AND constraints_fts MATCH :query
        ORDER BY rank ASC
        LIMIT :limit;
    """
    try:
        rows = session.exec(text(sql), params={"repo_id": repo_id, "query": fts_query, "limit": limit}).all()
        return [(str(row[0]), idx + 1) for idx, row in enumerate(rows)]
    except Exception as e:
        logger.warning("FTS search error, falling back to LIKE query", error=str(e))
        # Fallback to simple LIKE
        like_query = f"%{words[0]}%"
        fallback_sql = """
            SELECT id FROM constraints
            WHERE repo_id = :repo_id
              AND (title LIKE :q OR rule LIKE :q OR why LIKE :q)
            LIMIT :limit;
        """
        rows = session.exec(text(fallback_sql), params={"repo_id": repo_id, "q": like_query, "limit": limit}).all()
        return [(str(row[0]), idx + 1) for idx, row in enumerate(rows)]


def _vector_search(
    repo_id: str,
    query_vector: List[float],
    session: Session,
    limit: int = 20,
) -> List[Tuple[str, int]]:
    """Compute cosine similarity against constraint embeddings and return (constraint_id, rank)."""
    # Get all embeddings for constraints of this repo
    sql = """
        SELECT ce.constraint_id, ce.vector
        FROM constraint_embeddings ce
        JOIN constraints c ON c.id = ce.constraint_id
        WHERE c.repo_id = :repo_id;
    """
    rows = session.exec(text(sql), params={"repo_id": repo_id}).all()
    if not rows:
        return []

    scored_items: List[Tuple[str, float]] = []
    for c_id, blob in rows:
        if not blob:
            continue
        try:
            vec = np.frombuffer(blob, dtype=np.float32).tolist()
            sim = cosine_similarity(query_vector, vec)
            scored_items.append((str(c_id), sim))
        except Exception:
            continue

    # Sort descending by similarity
    scored_items.sort(key=lambda x: x[1], reverse=True)
    return [(item[0], idx + 1) for idx, item in enumerate(scored_items[:limit])]


def search_constraints(
    repo_id: str,
    query: str,
    session: Session,
    path: Optional[str] = None,
    status: Optional[str] = "active",
    severity: Optional[str] = None,
    top_k: int = 10,
    rrf_k: int = 60,
) -> List[ConstraintSchema]:
    """Hybrid retrieval of constraints using FTS5 (BM25) and vector embeddings with RRF fusion."""
    rrf_scores: Dict[str, float] = {}

    # 1. FTS5 BM25 search
    fts_ranks = _fts_search(repo_id, query, session, limit=top_k * 2)
    for c_id, rank in fts_ranks:
        rrf_scores[c_id] = rrf_scores.get(c_id, 0.0) + (1.0 / (rrf_k + rank))

    # 2. Vector search
    query_embeddings = compute_embeddings_sync([query])
    if query_embeddings:
        vec_ranks = _vector_search(repo_id, query_embeddings[0], session, limit=top_k * 2)
        for c_id, rank in vec_ranks:
            rrf_scores[c_id] = rrf_scores.get(c_id, 0.0) + (1.0 / (rrf_k + rank))

    # 3. Path scope matching & severity boosting
    candidates: List[Tuple[str, float]] = []
    for c_id, score in rrf_scores.items():
        c = get_constraint(c_id, session)
        if not c:
            continue

        # Status filter
        if status and c.status != status:
            continue
        # Severity filter
        if severity and c.severity != severity:
            continue

        boosted_score = score

        # Path scope boost
        if path:
            path_match = False
            for p in c.scope.paths:
                clean_p = p.replace("**", "").replace("*", "").strip("/")
                clean_target = path.strip("/")
                if clean_p in clean_target or clean_target in clean_p:
                    path_match = True
                    break
            if path_match:
                boosted_score += 0.025  # Substantial RRF boost

        # Severity boost
        if c.severity == "block":
            boosted_score += 0.010
        elif c.severity == "warn":
            boosted_score += 0.005

        candidates.append((c_id, boosted_score))

    # Sort candidates by combined score descending
    candidates.sort(key=lambda x: x[1], reverse=True)

    # Fetch full schemas for top-k
    results: List[ConstraintSchema] = []
    for c_id, _ in candidates[:top_k]:
        c_schema = get_constraint(c_id, session)
        if c_schema:
            results.append(c_schema)

    # If no results from hybrid search (e.g. empty index or very broad query), fallback to list
    if not results:
        all_repo_constraints = session.exec(
            select(Constraint).where(Constraint.repo_id == repo_id)
        ).all()
        for db_c in all_repo_constraints[:top_k]:
            c_schema = get_constraint(db_c.id, session)
            if c_schema:
                results.append(c_schema)

    return results
