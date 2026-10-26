from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


# Intent & Proofs
class IntentItem(BaseModel):
    id: str
    text: str
    testable: bool
    kind: Literal["bugfix", "feature", "refactor"]


class ProofItem(BaseModel):
    criterion_id: str
    test_name: str
    base: Literal["PASS", "FAIL", "ERROR"]
    head: Literal["PASS", "FAIL", "ERROR"]
    vacuous: bool
    artifact_id: Optional[str] = None


class SuiteCount(BaseModel):
    passed: int
    failed: int


class SuiteResults(BaseModel):
    base: SuiteCount
    head: SuiteCount
    regressions: List[str] = Field(default_factory=list)


class MutantSurvivor(BaseModel):
    file: str
    line: int
    op: str
    diff: str


class MutationResults(BaseModel):
    mutants: int
    killed: int
    survived: int
    timeout: int = 0
    score: float
    survivors: List[MutantSurvivor] = Field(default_factory=list)


# Evidence & Constraints
class EvidenceItem(BaseModel):
    type: Literal["revert", "incident_fix", "review", "comment"]
    url: str
    sha: Optional[str] = None
    excerpt: str
    at: Optional[str] = None


class ConstraintCheckSpec(BaseModel):
    kind: Literal["static", "test", "review"]
    spec: Dict[str, Any] = Field(default_factory=dict)


class ConstraintScope(BaseModel):
    paths: List[str] = Field(default_factory=list)
    symbols: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


class ConstraintSchema(BaseModel):
    id: str
    title: str
    rule: str
    why: str
    scope: ConstraintScope = Field(default_factory=ConstraintScope)
    severity: Literal["block", "warn", "info"] = "block"
    check: ConstraintCheckSpec = Field(default_factory=lambda: ConstraintCheckSpec(kind="static"))
    confidence: float = 1.0
    status: Literal["active", "proposed", "disputed", "deprecated"] = "active"
    evidence: List[EvidenceItem] = Field(default_factory=list)
    prevented_count: int = 0
    version: int = 1
    supersedes: List[str] = Field(default_factory=list)


class ConstraintResult(BaseModel):
    constraint_id: str
    title: str
    severity: Literal["block", "warn", "info"]
    result: Literal["PASS", "FAIL", "WARN", "NA"]
    evidence: List[EvidenceItem] = Field(default_factory=list)


class BrowserCheck(BaseModel):
    name: str
    result: Literal["PASS", "FAIL"]
    screenshot_artifact_id: Optional[str] = None


class BrowserResults(BaseModel):
    applicable: bool
    checks: List[BrowserCheck] = Field(default_factory=list)


class RepairIteration(BaseModel):
    iteration: int
    verdict: Literal["VERIFIED", "NEEDS_REVIEW", "REJECTED"]
    score: int
    failure_summary: str
    patch_artifact_id: Optional[str] = None


class ArtifactRef(BaseModel):
    id: str
    kind: Literal["log", "screenshot", "video", "diff", "test", "json"]
    url: str


class ScoreBreakdown(BaseModel):
    behavior: float
    constraints: float
    test_strength: float
    regression: float
    browser: Optional[float] = None


class PRInfo(BaseModel):
    number: int
    title: str
    author: str
    base_sha: str
    head_sha: str
    url: str


class ReceiptSchema(BaseModel):
    id: str
    slug: str
    repo: str
    pr: PRInfo
    verdict: Literal["VERIFIED", "NEEDS_REVIEW", "REJECTED"]
    score: int
    iterations: int = 1
    duration_ms: int
    intent: List[IntentItem] = Field(default_factory=list)
    proofs: List[ProofItem] = Field(default_factory=list)
    suite: SuiteResults
    mutation: MutationResults
    constraints: List[ConstraintResult] = Field(default_factory=list)
    browser: BrowserResults
    repair_history: List[RepairIteration] = Field(default_factory=list)
    score_breakdown: ScoreBreakdown
    limits: List[str] = Field(default_factory=list)
    artifacts: List[ArtifactRef] = Field(default_factory=list)
    created_at: str


# REST Endpoints schemas
class CreateRepoRequest(BaseModel):
    full_name: str
    default_branch: str = "main"


class RepoResponse(BaseModel):
    id: str
    full_name: str
    default_branch: str
    stack: Optional[str] = None
    last_ingested_at: Optional[datetime] = None


class CreateRunRequest(BaseModel):
    pr_number: int
    base_sha: str
    head_sha: str


class RunResponse(BaseModel):
    id: str
    repo_id: str
    pr_number: int
    base_sha: str
    head_sha: str
    state: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    iteration: int = 1


class BriefingRequest(BaseModel):
    task: str
    paths: List[str] = Field(default_factory=list)


class BriefingResponse(BaseModel):
    constraints: List[ConstraintSchema]
    preflight_checklist: List[str]
    suggested_tests: List[str]


class CheckDiffRequest(BaseModel):
    diff: str


class DiffViolation(BaseModel):
    constraint_id: str
    title: str
    severity: str
    file: str
    line: int
    hunk: str
    evidence_urls: List[str]


class CheckDiffResponse(BaseModel):
    violations: List[DiffViolation]
    passed: bool


class ConstraintFeedbackRequest(BaseModel):
    action: Literal["accept", "reject", "edit"]
    note: Optional[str] = None
    edited_rule: Optional[str] = None


class OutcomeRequest(BaseModel):
    human_decision: Literal["merged", "rejected", "overridden"]
    note: Optional[str] = None


class DocsSyncResponse(BaseModel):
    status: str
    pr_url: Optional[str] = None
    updated_files: List[str] = Field(default_factory=list)


class GraphNode(BaseModel):
    id: str
    type: str
    label: str
    severity: Optional[str] = None
    confidence: Optional[float] = None


class GraphEdge(BaseModel):
    src: str
    dst: str
    kind: str
    weight: float = 1.0


class GraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
