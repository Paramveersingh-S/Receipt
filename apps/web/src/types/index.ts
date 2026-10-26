export interface ProofItem {
  criterion_id: string;
  test_name: string;
  base: "PASS" | "FAIL" | "ERROR";
  head: "PASS" | "FAIL" | "ERROR";
  vacuous: boolean;
  artifact_id?: string;
}

export interface MutantSurvivor {
  file: string;
  line: number;
  op: string;
  diff: string;
}

export interface MutationResults {
  mutants: number;
  killed: number;
  survived: number;
  timeout: number;
  score: number;
  survivors: MutantSurvivor[];
}

export interface EvidenceItem {
  type: "revert" | "incident_fix" | "review" | "comment";
  url: string;
  sha?: string;
  excerpt: string;
  at?: string;
}

export interface ConstraintItem {
  id: string;
  title: string;
  rule: string;
  why: string;
  scope?: {
    paths: string[];
    symbols: string[];
    tags: string[];
  };
  severity: "block" | "warn" | "info";
  confidence: number;
  status: "active" | "proposed" | "disputed" | "deprecated";
  evidence: EvidenceItem[];
  prevented_count: number;
  version: number;
}

export interface ConstraintResult {
  constraint_id: string;
  title: string;
  severity: "block" | "warn" | "info";
  result: "PASS" | "FAIL" | "WARN" | "NA";
  evidence: EvidenceItem[];
}

export interface BrowserCheck {
  name: string;
  result: "PASS" | "FAIL";
  screenshot_artifact_id?: string;
}

export interface RepairIteration {
  iteration: number;
  verdict: "VERIFIED" | "NEEDS_REVIEW" | "REJECTED";
  score: number;
  failure_summary: string;
  patch_artifact_id?: string;
}

export interface Receipt {
  id: string;
  slug: string;
  repo: string;
  pr: {
    number: number;
    title: string;
    author: string;
    base_sha: string;
    head_sha: string;
    url: string;
  };
  verdict: "VERIFIED" | "NEEDS_REVIEW" | "REJECTED";
  score: number;
  iterations: number;
  duration_ms: number;
  intent: Array<{
    id: string;
    text: string;
    testable: boolean;
    kind: "bugfix" | "feature" | "refactor";
  }>;
  proofs: ProofItem[];
  suite: {
    base: { passed: number; failed: number };
    head: { passed: number; failed: number };
    regressions: string[];
  };
  mutation: MutationResults;
  constraints: ConstraintResult[];
  browser: {
    applicable: boolean;
    checks: BrowserCheck[];
  };
  repair_history: RepairIteration[];
  score_breakdown: {
    behavior: number;
    constraints: number;
    test_strength: number;
    regression: number;
    browser?: number | null;
  };
  limits: string[];
  artifacts: Array<{ id: string; kind: string; url: string }>;
  created_at: string;
}

export interface SSEEvent {
  seq: number;
  type: string;
  at: string;
  payload: any;
}

export interface GraphNode {
  id: string;
  type: "constraint" | "file" | "pr" | "revert" | "incident";
  label: string;
  severity?: string;
  confidence?: number;
}

export interface GraphEdge {
  src: string;
  dst: string;
  kind: string;
  weight: number;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface BenchmarkComparison {
  system: string;
  detection_rate: number;
  false_positive_rate: number;
  precision: number;
  f1_score: number;
  mean_duration_secs: number;
  mean_cost_usd: number;
  repair_success_rate: number;
}

export interface BenchmarkResults {
  summary: {
    total_tasks: number;
    evaluated_repos: string[];
    completed_at: string;
  };
  comparisons: BenchmarkComparison[];
  scar_eval: {
    planted_lessons_count: number;
    recovered_lessons_count: number;
    recall: number;
    precision: number;
    false_positives: number;
  };
}
