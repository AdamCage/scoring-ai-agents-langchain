export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || response.statusText);
  }
  return response.json();
}

export type Health = {
  status: string;
  scoring_model: string;
  vector_index: string;
  vector_backend?: string;
  knowledge_base: number;
  llm_provider: string;
  llm_configured: boolean;
  observability: string;
  langsmith: string;
  langfuse: string;
  langsmith_url?: string | null;
  langsmith_experiment?: { status: string; url?: string | null; experiment?: string; dataset?: string };
  langfuse_url?: string | null;
  build: string;
  environment: string;
};

export type Application = {
  application_id: string;
  company_name: string;
  segment: "sme" | "retail";
  industry: string;
  region: string;
  company_age_months: number;
  annual_revenue: number;
  revenue_growth: number;
  ebitda_margin: number;
  debt_to_revenue: number;
  requested_amount: number;
  requested_term: number;
  credit_history_months: number;
  overdue_30d_count: number;
  overdue_90d_count: number;
  bureau_score: number;
  existing_loans_count: number;
  industry_risk: number;
  region_risk: number;
};

export type Preset = {
  id: string;
  title: string;
  subtitle: string;
  scenario: string;
  application: Application;
};

export type SSEEvent = {
  type: string;
  node: string | null;
  run_id: string;
  timestamp_ms: number;
  data: Record<string, unknown>;
};

export type SpanEvent = {
  name: string;
  payload?: Record<string, unknown>;
};

export type Span = {
  span_id: string;
  name: string;
  kind: string;
  status: string;
  duration_ms?: number | null;
  code_path?: string | null;
  mmd_node?: string | null;
  error?: string | null;
  events: SpanEvent[];
};

export type Trace = {
  trace_id: string;
  run_id: string;
  name: string;
  duration_ms?: number | null;
  status: string;
  started_at: string;
  metadata: Record<string, unknown>;
  spans: Span[];
};

export type Experiment = {
  run_id: string;
  experiment: string;
  started_at: string;
  summary: Record<string, number>;
  status: string;
};

export type EvalVariant = {
  name: string;
  retrieval: string;
  reranker: boolean;
  prompt: string;
  expected_gate: "pass" | "fail";
};

export type VariantResult = {
  summary: Record<string, number>;
  gate: { passed: boolean; failed: string[] };
  expected_gate: string;
};

export type EvalsResponse = {
  summary: Record<string, unknown>;
  experiments: Experiment[];
  gate: { passed: boolean; failed: string[] } | null;
  thresholds: Record<string, number>;
  variants?: EvalVariant[];
  latest_by_variant?: Record<string, VariantResult>;
  langfuse_url?: string | null;
  langsmith_experiment?: { status: string; url?: string | null; experiment?: string; dataset?: string };
};
