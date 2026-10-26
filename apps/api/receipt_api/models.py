import datetime
from typing import Optional
from sqlmodel import Field, SQLModel


class Repo(SQLModel, table=True):
    __tablename__ = "repos"

    id: str = Field(primary_key=True)
    full_name: str = Field(index=True)
    default_branch: str = Field(default="main")
    stack: Optional[str] = Field(default=None)  # python | node
    last_ingested_at: Optional[datetime.datetime] = Field(default=None)
    settings_json: str = Field(default="{}")


class GHEvent(SQLModel, table=True):
    __tablename__ = "gh_events"

    id: str = Field(primary_key=True)
    repo_id: str = Field(index=True)
    kind: str = Field(index=True)  # pr | review_comment | review | commit | issue | revert
    gh_id: str = Field(index=True)
    url: str
    author: str
    created_at: datetime.datetime
    payload_json: str = Field(default="{}")


class Lesson(SQLModel, table=True):
    __tablename__ = "lessons"

    id: str = Field(primary_key=True)
    repo_id: str = Field(index=True)
    source_event_ids: str = Field(default="[]")  # JSON list of event ids
    raw_text: str
    extracted_json: str = Field(default="{}")
    status: str = Field(default="candidate")  # candidate | clustered | rejected


class Constraint(SQLModel, table=True):
    __tablename__ = "constraints"

    id: str = Field(primary_key=True)
    repo_id: str = Field(index=True)
    title: str
    rule: str
    why: str
    scope_json: str = Field(default="{}")  # paths, symbols, tags
    severity: str = Field(default="block")  # block | warn | info
    check_json: str = Field(default="{}")  # static, test, review
    confidence: float = Field(default=1.0)
    status: str = Field(default="active")  # active | proposed | disputed | deprecated
    version: int = Field(default=1)
    supersedes_json: str = Field(default="[]")
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    last_confirmed_at: Optional[datetime.datetime] = Field(default=None)
    prevented_count: int = Field(default=0)


ConstraintRecord = Constraint


class ConstraintEvidence(SQLModel, table=True):
    __tablename__ = "constraint_evidence"

    id: str = Field(primary_key=True)
    constraint_id: str = Field(index=True)
    type: str  # revert | incident_fix | review | comment
    url: str
    sha: Optional[str] = None
    excerpt: str
    at: Optional[datetime.datetime] = None


class ConstraintEmbedding(SQLModel, table=True):
    __tablename__ = "constraint_embeddings"

    constraint_id: str = Field(primary_key=True)
    vector: bytes  # float32 binary blob


class Edge(SQLModel, table=True):
    __tablename__ = "edges"

    id: Optional[int] = Field(default=None, primary_key=True)
    src_type: str = Field(index=True)
    src_id: str = Field(index=True)
    dst_type: str = Field(index=True)
    dst_id: str = Field(index=True)
    kind: str = Field(index=True)  # scopes_file | extracted_from | prevents_incident | reverted
    weight: float = Field(default=1.0)


class Run(SQLModel, table=True):
    __tablename__ = "runs"

    id: str = Field(primary_key=True)
    repo_id: str = Field(index=True)
    pr_number: int = Field(index=True)
    base_sha: str
    head_sha: str
    state: str = Field(default="pending")  # pending | running | completed | failed | cancelled
    started_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    finished_at: Optional[datetime.datetime] = None
    iteration: int = Field(default=1)
    parent_run_id: Optional[str] = None


class RunStep(SQLModel, table=True):
    __tablename__ = "run_steps"

    id: str = Field(primary_key=True)
    run_id: str = Field(index=True)
    name: str = Field(index=True)
    state: str = Field(default="pending")  # pending | running | passed | failed | skipped
    started_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    finished_at: Optional[datetime.datetime] = None
    summary_json: str = Field(default="{}")


class RunEvent(SQLModel, table=True):
    __tablename__ = "run_events"

    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: str = Field(index=True)
    seq: int = Field(index=True)
    type: str = Field(index=True)
    payload_json: str = Field(default="{}")
    at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))


class Artifact(SQLModel, table=True):
    __tablename__ = "artifacts"

    id: str = Field(primary_key=True)
    run_id: str = Field(index=True)
    kind: str = Field(index=True)  # log | screenshot | video | diff | test | json
    path: str
    meta_json: str = Field(default="{}")


class ReceiptRecord(SQLModel, table=True):
    __tablename__ = "receipts"

    id: str = Field(primary_key=True)
    run_id: str = Field(index=True, unique=True)
    verdict: str = Field(index=True)  # VERIFIED | NEEDS_REVIEW | REJECTED
    score: int
    receipt_json: str  # full receipt json matching contract
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    public_slug: str = Field(index=True, unique=True)


class Outcome(SQLModel, table=True):
    __tablename__ = "outcomes"

    id: str = Field(primary_key=True)
    receipt_id: str = Field(index=True)
    human_decision: str  # merged | rejected | overridden
    at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    note: Optional[str] = None


class DocsPage(SQLModel, table=True):
    __tablename__ = "docs_pages"

    id: str = Field(primary_key=True)
    repo_id: str = Field(index=True)
    slug: str = Field(index=True)
    markdown: str
    generated_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    source_constraint_ids: str = Field(default="[]")


class Job(SQLModel, table=True):
    __tablename__ = "jobs"

    id: str = Field(primary_key=True)
    kind: str = Field(index=True)
    payload_json: str = Field(default="{}")
    state: str = Field(default="queued")  # queued | running | completed | failed | cancelled
    attempts: int = Field(default=0)
    run_after: Optional[datetime.datetime] = None
    locked_by: Optional[str] = None


# Aliases for backward and forward compatibility
DBReceipt = ReceiptRecord
DBRun = Run
DBRunStep = RunStep
DBRunEvent = RunEvent
DBRepo = Repo

