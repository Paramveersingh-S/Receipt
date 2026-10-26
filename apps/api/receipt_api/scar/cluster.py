import json
import structlog
from typing import Dict, List, Set
from receipt_api.llm.embeddings import cosine_similarity, _deterministic_hash_vector
from receipt_api.scar.score import calculate_constraint_confidence
from receipt_api.schemas import ConstraintSchema, EvidenceItem

logger = structlog.get_logger(__name__)


def cluster_and_deduplicate_constraints(
    candidates: List[ConstraintSchema],
    similarity_threshold: float = 0.75,
) -> List[ConstraintSchema]:
    """Cluster similar constraints, deduplicate rules, merge evidence, and detect supersedes.
    
    Returns a list of canonical, high-confidence ConstraintSchema objects.
    """
    if not candidates:
        return []

    clusters: List[List[ConstraintSchema]] = []
    cluster_vectors: List[List[float]] = []

    for candidate in candidates:
        cand_text = f"{candidate.title} {candidate.rule} {candidate.why}"
        cand_vec = _deterministic_hash_vector(cand_text)

        matched_cluster_idx = -1
        highest_sim = 0.0

        for idx, cluster_vec in enumerate(cluster_vectors):
            sim = cosine_similarity(cand_vec, cluster_vec)
            if sim > similarity_threshold and sim > highest_sim:
                highest_sim = sim
                matched_cluster_idx = idx

        if matched_cluster_idx >= 0:
            clusters[matched_cluster_idx].append(candidate)
        else:
            clusters.append([candidate])
            cluster_vectors.append(cand_vec)

    canonical_constraints: List[ConstraintSchema] = []

    for cluster in clusters:
        # Sort so that highest severity, most evidence, or highest confidence is first
        cluster.sort(
            key=lambda c: (1 if c.severity == "block" else 0, len(c.evidence), c.confidence),
            reverse=True,
        )
        canonical = cluster[0]

        # Merge evidence items uniquely
        merged_evidence: List[EvidenceItem] = []
        seen_keys: Set[str] = set()

        for member in cluster:
            for ev in member.evidence:
                key = f"{ev.type}:{ev.url}:{ev.sha or ''}:{ev.excerpt[:30]}"
                if key not in seen_keys:
                    seen_keys.add(key)
                    merged_evidence.append(ev)

        # Merge scopes
        all_paths = set(canonical.scope.paths)
        all_symbols = set(canonical.scope.symbols)
        all_tags = set(canonical.scope.tags)
        for member in cluster[1:]:
            all_paths.update(member.scope.paths)
            all_symbols.update(member.scope.symbols)
            all_tags.update(member.scope.tags)

        # Check for supersedes / superseded ids
        superseded_ids = [m.id for m in cluster[1:] if m.id != canonical.id]

        # Re-calculate confidence based on merged evidence
        new_confidence = calculate_constraint_confidence(merged_evidence)

        canonical.evidence = merged_evidence
        canonical.scope.paths = sorted(list(all_paths))
        canonical.scope.symbols = sorted(list(all_symbols))
        canonical.scope.tags = sorted(list(all_tags))
        canonical.confidence = new_confidence
        canonical.supersedes = superseded_ids

        canonical_constraints.append(canonical)

    return canonical_constraints
