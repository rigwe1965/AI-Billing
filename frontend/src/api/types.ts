export type UserRole = "admin_finance" | "dept_lead";

export interface User {
  id: number;
  email: string;
  role: UserRole;
  department_id: number | null;
  is_active: boolean;
}

export interface Department {
  id: number;
  name: string;
  code: string;
  is_active: boolean;
}

export interface Provider {
  id: number;
  name: string;
  code: string;
  connector_type: string;
}

export interface PricingRate {
  id: number;
  provider_id: number;
  sku_code: string;
  unit: string;
  rate_amount: string;
  currency: string;
  effective_from: string;
  effective_to: string | null;
  source: string;
}

export interface CsvImportResult {
  usage_records_created: number;
  cost_line_items_created: number;
  needs_pricing_rule_count: number;
}

export interface CostSummaryRow {
  period: string;
  department: string | null;
  provider: string;
  total_amount: string;
  currency: string;
}

export interface UnpricedUsageRow {
  cost_line_item_id: number;
  usage_record_id: number;
  provider: string;
  sku_code: string;
  quantity: string;
  period_start: string;
  reason: string;
}

export interface ApiKeyMap {
  id: number;
  provider_id: number;
  api_key_label: string;
  department_id: number;
  effective_from: string;
  effective_to: string | null;
}

export interface TagMap {
  id: number;
  provider_id: number;
  tag_value: string;
  department_id: number;
  effective_from: string;
  effective_to: string | null;
}

export interface ManualAllocation {
  id: number;
  usage_record_id: number;
  department_id: number;
  allocation_percent: string;
  note: string | null;
}

export interface ConnectorStatus {
  provider_code: string;
  configured: boolean;
  supports_usage_pull: boolean;
  supports_cost_reconciliation: boolean;
  requires_prerequisite: string | null;
  unavailable_reason: string | null;
}

export interface ConnectionTestResult {
  provider_code: string;
  ok: boolean;
  detail: string;
}

export interface PullResult {
  usage_records_created: number;
  cost_line_items_created: number;
  needs_pricing_rule_count: number;
  needs_allocation_count: number;
}

export interface Budget {
  id: number;
  department_id: number;
  period: string;
  amount: string;
  currency: string;
}

export interface BudgetStatus {
  budget_id: number;
  department_id: number;
  department_name: string;
  period: string;
  amount: string;
  current_spend: string;
  percent_used: string;
  currency: string;
}

export interface AskInsightRequest {
  question: string;
}

export interface AskInsightResponse {
  answer: string;
}

export interface Alert {
  id: number;
  budget_id: number;
  threshold_percent: number;
  triggered_at: string;
  current_spend_amount: string;
  status: "open" | "acknowledged";
  notified_via: string;
}
