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

export interface Evaluation {
  id: number;
  job_id: number;
  total_score: number | null;
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
  unknowns: string[];
  questions: string[];
  hard_filters_triggered: string[];
  evaluation_version: string;
  prompt_version: string | null;
  model: string | null;
  evaluated_at: string;
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
  position_nature?: string;
  salary_text?: string | null;
  salary_min?: number | null;
  salary_max?: number | null;
  degree_requirement?: string | null;
  experience_requirement?: string | null;
  source_url?: string | null;
  status?: string;
  allow_duplicate?: boolean;
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
