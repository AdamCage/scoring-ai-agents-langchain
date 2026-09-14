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

export function takeSseEvents<T = SSEEvent>(buffer: string): { events: T[]; rest: string } {
  const chunks = buffer.split("\n\n");
  const rest = chunks.pop() || "";
  const events: T[] = [];
  for (const chunk of chunks) {
    const dataLine = chunk.split("\n").find((line) => line.startsWith("data:"));
    if (!dataLine) continue;
    events.push(JSON.parse(dataLine.slice(5).trim()) as T);
  }
  return { events, rest };
}

export type Health = {
  status: string;
  scoring_model: string;
  vector_index: string;
  knowledge_base: number;
  llm_provider: string;
  llm_configured: boolean;
  observability: string;
  langsmith: string;
  langfuse: string;
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
  timestamp?: string;
};

export type Generation = {
  span_id: string;
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  input_preview: string;
  output_preview: string;
};

export type Span = {
  span_id: string;
  parent_span_id?: string | null;
  name: string;
  kind: string;
  status: string;
  started_at?: string;
  ended_at?: string | null;
  duration_ms?: number | null;
  attributes?: Record<string, unknown>;
  code_path?: string | null;
  mmd_node?: string | null;
  error?: string | null;
  events: SpanEvent[];
  generations?: Generation[];
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

export type GraphNode = {
  id: string;
  mmd: string;
  label: string;
  tech: string;
  kind: string;
  optional?: boolean;
  parallel_group?: string;
};

export type GraphEdge = {
  source: string;
  target: string;
  label?: string;
};

export type GraphDefinition = {
  nodes: GraphNode[];
  edges: GraphEdge[];
  happy_path: string[];
  mermaid: string;
  node_meta: Record<string, { code_path: string; mmd_node: string }>;
};

export type Experiment = {
  run_id: string;
  experiment: string;
  started_at: string;
  summary: Record<string, number>;
  status: string;
};

export type EvalCase = {
  case_id: string;
  dataset: string;
  metric: string;
  score: number;
  passed: boolean;
  comment: string;
  details: Record<string, unknown>;
  run_id?: string;
};

export type EvalsResponse = {
  summary: Record<string, unknown>;
  experiments: Experiment[];
  results: EvalCase[];
  gate: { passed: boolean; failed: string[] } | null;
  thresholds: Record<string, number>;
};
