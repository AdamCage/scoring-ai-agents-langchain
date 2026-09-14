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
