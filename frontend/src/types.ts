export interface Organization {
  id: number;
  name: string;
  organization_type: string | null;
  province: string | null;
  city: string | null;
  official_url: string | null;
  career_url: string | null;
  notes: string | null;
  job_count: number;
  created_at: string;
  updated_at: string;
}

export interface RiskItem {
  type: string;
  severity: string;
  reason: string;
  evidence_ids: number[];
}

export interface AcademicJobDetails {
  establishment_status: string;
  tenure_status: string;
  contract_type: string;
  funding_source: string;
  contract_years: number | null;
  first_contract_period: string | null;
  is_up_or_out: boolean | null;
  midterm_review: string | null;
  final_review: string | null;
  publication_requirements: string | null;
  grant_requirements: string | null;
  teaching_requirements: string | null;
  admin_requirements: string | null;
  current_title: string | null;
  promotion_path: string | null;
  independent_pi: boolean | null;
  lab_space: string | null;
  startup_funding: string | null;
  startup_funding_terms: string | null;
  can_supervise_master: boolean | null;
  can_supervise_phd: boolean | null;
  master_quota: string | null;
  phd_quota: string | null;
  fixed_income: string | null;
  performance_income: string | null;
  housing_settlement: string | null;
  housing_subsidy: string | null;
  talent_housing: string | null;
  regional_talent_subsidy: string | null;
  created_at: string;
  updated_at: string;
}

export interface Evaluation {
  id: number;
  job_id: number;
  total_score: number | null;
  score_coverage: number | null;
  provider: string | null;
  fit_score: number | null;
  career_stability_score: number | null;
  research_resources_score: number | null;
  region_score: number | null;
  compensation_score: number | null;
  reputation_score: number | null;
  workload_score: number | null;
  long_term_score: number | null;
  recommendation_level: string | null;
  risk_level: string | null;
  confidence_level: string | null;
  summary: string | null;
  strengths: string[];
  weaknesses: string[];
  risks: string[];
  risk_items: RiskItem[];
  unknowns: string[];
  questions: string[];
  hard_filters_triggered: string[];
  evaluation_version: string;
  prompt_version: string | null;
  model: string | null;
  evaluated_at: string;
  profile_hash: string | null;
  scoring_config_hash: string | null;
  region_config_hash: string | null;
  evidence_items: {
    id: number;
    claim: string;
    evidence_level: string;
    source_type: string | null;
    scope_level: string | null;
    stance: string | null;
  }[];
}

export interface JobListItem {
  id: number;
  title: string;
  department: string | null;
  job_category: string;
  province: string | null;
  city: string | null;
  status: string;
  position_nature: string;
  salary_text: string | null;
  salary_min: number | null;
  salary_max: number | null;
  deadline: string | null;
  first_seen_at: string;
  source: string;
  user_rating: number | null;
  organization: {
    id: number;
    name: string;
    organization_type: string | null;
    province: string | null;
    city: string | null;
  } | null;
  evaluation: Evaluation | null;
}

export interface JobVersion {
  id: number;
  content_hash: string;
  description: string | null;
  salary_text: string | null;
  deadline: string | null;
  changes: { field: string; old: string | null; new: string | null }[];
  captured_at: string;
}

export interface JobDetail extends JobListItem {
  country: string | null;
  description_raw: string | null;
  description_clean: string | null;
  posted_at: string | null;
  employment_type: string | null;
  degree_requirement: string | null;
  experience_requirement: string | null;
  source_url: string | null;
  user_priority: number | null;
  user_notes: string | null;
  fingerprint: string;
  created_at: string;
  updated_at: string;
  versions: JobVersion[];
  has_version_changes: boolean;
  academic_details: AcademicJobDetails | null;
}

export interface JobCreateInput {
  title: string;
  organization_id?: number | null;
  organization_name?: string | null;
  department?: string | null;
  job_category?: string;
  country?: string | null;
  province?: string | null;
  city?: string | null;
  description_raw?: string | null;
  posted_at?: string | null;
  deadline?: string | null;
  employment_type?: string | null;
  salary_text?: string | null;
  salary_currency?: string | null;
  salary_period?: string | null;
  salary_min?: number | null;
  salary_max?: number | null;
  degree_requirement?: string | null;
  experience_requirement?: string | null;
  source_url?: string | null;
  status?: string;
  academic_details?: Partial<AcademicJobDetails> | null;
  import_audit?: ImportAuditInput | null;
  allow_duplicate?: boolean;
}

export interface ImportAuditInput {
  ingestion_method: "text" | "url" | "manual";
  source_url: string | null;
  provider: string | null;
  model: string | null;
  prompt_version: string | null;
  extraction_json: Record<string, unknown> | null;
}

export interface JobExtraction {
  title: string;
  organization: string | null;
  department: string | null;
  job_category: string;
  country: string | null;
  province: string | null;
  city: string | null;
  employment_type: string | null;
  posted_at: string | null;
  deadline: string | null;
  salary_text: string | null;
  salary_currency: string | null;
  salary_period: string | null;
  degree_requirement: string | null;
  experience_requirement: string | null;
  establishment_status: string;
  tenure_status: string;
  contract_type: string;
  funding_source: string;
  is_up_or_out: boolean | null;
  contract_years: number | null;
  first_contract_period: string | null;
  midterm_review: string | null;
  final_review: string | null;
  publication_requirements: string | null;
  grant_requirements: string | null;
  teaching_requirements: string | null;
  admin_requirements: string | null;
  current_title: string | null;
  promotion_path: string | null;
  independent_pi: boolean | null;
  lab_space: string | null;
  startup_funding: string | null;
  startup_funding_terms: string | null;
  can_supervise_master: boolean | null;
  can_supervise_phd: boolean | null;
  master_quota: string | null;
  phd_quota: string | null;
  fixed_income: string | null;
  performance_income: string | null;
  housing_settlement: string | null;
  housing_subsidy: string | null;
  talent_housing: string | null;
  regional_talent_subsidy: string | null;
  unknowns: string[];
}

export interface ExtractionPreview {
  source_type: "text" | "url";
  source_url: string | null;
  source_text: string;
  extraction: JobExtraction;
  provider: string;
  model: string | null;
  prompt_version: string;
}

export interface JobUpdateInput {
  title?: string;
  status?: string;
  user_rating?: number | null;
  user_priority?: number | null;
  user_notes?: string | null;
  salary_text?: string | null;
  deadline?: string | null;
  description_raw?: string | null;
  [key: string]: unknown;
}

export interface DashboardCounts {
  new_today: number;
  to_review: number;
  high_match: number;
  focus: number;
  preparing: number;
  applied: number;
  interviewing: number;
  offer: number;
}

export interface Dashboard {
  counts: DashboardCounts;
  top_jobs: JobListItem[];
}

export interface ApplicationJobBrief {
  id: number;
  title: string;
  organization_name: string | null;
  department: string | null;
  city: string | null;
  deadline: string | null;
  total_score: number | null;
  recommendation_level: string | null;
}

export interface Application {
  id: number;
  job_id: number;
  status: string;
  priority: number | null;
  applied_at: string | null;
  resume_version: string | null;
  cover_letter_version: string | null;
  contact: string | null;
  notes: string | null;
  next_action: string | null;
  next_action_date: string | null;
  created_at: string;
  updated_at: string;
  job: ApplicationJobBrief | null;
  allowed_next_statuses: string[];
}

export interface ApplicationCreateInput {
  status?: string;
  priority?: number | null;
  resume_version?: string | null;
  cover_letter_version?: string | null;
  contact?: string | null;
  notes?: string | null;
  next_action?: string | null;
  next_action_date?: string | null;
}

export interface ApplicationUpdateInput extends ApplicationCreateInput {}

export interface Evidence {
  id: number;
  job_id: number | null;
  organization_id: number | null;
  category: string;
  claim: string;
  source_type: string | null;
  source_url: string | null;
  source_title: string | null;
  source_author: string | null;
  is_firsthand: boolean | null;
  independence_key: string | null;
  repost_of_evidence_id: number | null;
  stance: string;
  scope_level: string;
  scope_name: string | null;
  evidence_level: string;
  published_at: string | null;
  collected_at: string;
  confidence: string | null;
  raw_excerpt: string | null;
  created_at: string;
}

export interface EvidenceCreateInput {
  claim: string;
  category?: string;
  source_type?: string | null;
  source_url?: string | null;
  source_title?: string | null;
  source_author?: string | null;
  is_firsthand?: boolean | null;
  independence_key?: string | null;
  repost_of_evidence_id?: number | null;
  stance?: string;
  scope_level?: string;
  scope_name?: string | null;
  evidence_level?: string;
  published_at?: string | null;
  confidence?: string | null;
  raw_excerpt?: string | null;
  organization_id?: number | null;
}

export interface ReputationTopicStat {
  topic: string;
  positive_sources: number;
  negative_sources: number;
  independent_sources: number;
  evidence_levels: string[];
  time_start: string | null;
  time_end: string | null;
  eligible_for_scoring: boolean;
  eligible_reason: string;
  evidence_ids: number[];
  ai_conclusion: string | null;
}

export interface ReputationReport {
  organization_id: number;
  organization_name: string;
  department: string | null;
  topics: ReputationTopicStat[];
  clues: { evidence_id: number; claim: string; reason: string }[];
  overall_confidence: string;
  synthesized_by_ai: boolean;
  prompt_version: string | null;
  generated_at: string;
}

export interface SettingsData {
  "scoring.yaml": { scoring: Record<string, number>; recommendation?: unknown; region_tier_scores?: Record<string, number> };
  "regions.yaml": { preferred: string[]; acceptable: string[]; neutral: string[]; avoid: string[]; city_details?: Record<string, unknown> };
  "profile.yaml": { hard_filters: Record<string, unknown>; research_interests?: string[]; skills?: string[] };
}

export interface ReEvaluateResult {
  total: number;
  succeeded: number[];
  failed: { job_id: number; error: string }[];
}

export interface CollectorRunItem {
  id: number;
  source_id: string;
  source_name: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  fetched_count: number;
  new_count: number;
  duplicate_count: number;
  possible_duplicate_count: number;
  filtered_count: number;
  error_message: string | null;
}

export interface CollectorRun {
  id: number;
  status: string;
  started_at: string;
  finished_at: string | null;
  trigger: string;
  source_count: number;
  completed_source_count: number;
  discovered_count: number;
  new_count: number;
  duplicate_count: number;
  possible_duplicate_count: number;
  filtered_count: number;
  failed_source_count: number;
  items: CollectorRunItem[];
}

export interface DiscoveredJob {
  id: number;
  source_id: string;
  source_name: string;
  source_job_id: string | null;
  source_url: string;
  canonical_url: string | null;
  title_raw: string | null;
  description_raw: string | null;
  published_at_raw: string | null;
  organization_hint: string | null;
  location_hint: string | null;
  status: string;
  discovered_at: string;
  last_seen_at: string;
  first_run_id: number | null;
  last_run_id: number | null;
  possible_duplicate_of_id: number | null;
  duplicate_reason: string | null;
  imported_job_id: number | null;
  raw_payload: unknown;
}

export interface DiscoveredJobList {
  items: DiscoveredJob[];
  total: number;
}
