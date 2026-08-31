export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(status: number, message: string, body: unknown) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail: unknown = null;
    try {
      detail = (await res.json()).detail ?? null;
    } catch {
      /* 非 JSON 错误体 */
    }
    const message =
      typeof detail === "string"
        ? detail
        : detail && typeof detail === "object" && "message" in detail
          ? String((detail as { message: unknown }).message)
          : `${res.status} ${res.statusText}`;
    throw new ApiError(res.status, message, detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export interface JobQueryParams {
  q?: string;
  job_category?: string;
  status?: string;
  province?: string;
  city?: string;
  organization_id?: number;
  recommendation?: string;
  risk_level?: string;
  confidence?: string;
  min_score?: number;
  max_score?: number;
  sort?: string;
  order?: string;
  page?: number;
  page_size?: number;
}

export function buildQuery(params: Record<string, unknown>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    search.set(key, String(value));
  }
  const s = search.toString();
  return s ? `?${s}` : "";
}

export async function extractPreview(payload: {
  text?: string;
  url?: string;
}): Promise<import("../types").ExtractionPreview> {
  return api("/jobs/extract-preview", { method: "POST", body: JSON.stringify(payload) });
}

export async function evaluateJob(jobId: number): Promise<import("../types").Evaluation> {
  return api(`/jobs/${jobId}/evaluate`, { method: "POST" });
}

export async function listApplications(params: { status?: string; q?: string; sort?: string } = {}) {
  return api<{ items: import("../types").Application[]; total: number }>(
    `/applications${buildQuery(params)}`,
  );
}

export async function getApplicationByJob(jobId: number): Promise<import("../types").Application | null> {
  return api(`/jobs/${jobId}/application`);
}

export async function createApplication(jobId: number, payload: import("../types").ApplicationCreateInput = {}) {
  return api<import("../types").Application>(`/jobs/${jobId}/application`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateApplication(
  applicationId: number,
  payload: import("../types").ApplicationUpdateInput,
) {
  return api<import("../types").Application>(`/applications/${applicationId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function deleteApplication(applicationId: number) {
  return api<void>(`/applications/${applicationId}`, { method: "DELETE" });
}

export async function listEvidence(params: { job_id?: number; organization_id?: number; category?: string }) {
  return api<import("../types").Evidence[]>(`/evidence${buildQuery(params)}`);
}

export async function createJobEvidence(jobId: number, payload: import("../types").EvidenceCreateInput) {
  return api<import("../types").Evidence>(`/evidence/jobs/${jobId}`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function createOrgEvidence(orgId: number, payload: import("../types").EvidenceCreateInput) {
  return api<import("../types").Evidence>(`/evidence/organizations/${orgId}`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function deleteEvidence(evidenceId: number) {
  return api<void>(`/evidence/${evidenceId}`, { method: "DELETE" });
}

export async function getReputationReport(orgId: number, department?: string | null) {
  return api<import("../types").ReputationReport>(
    `/organizations/${orgId}/reputation${buildQuery({ department })}`,
  );
}

export async function synthesizeReputation(orgId: number, department?: string | null) {
  return api<import("../types").ReputationReport>(
    `/organizations/${orgId}/reputation/synthesize${buildQuery({ department })}`,
    { method: "POST" },
  );
}

export async function getSettings() {
  return api<import("../types").SettingsData>("/settings");
}

export async function updateSettings(payload: {
  scoring_yaml?: unknown;
  regions_yaml?: unknown;
  profile_yaml?: unknown;
}) {
  return api<{ written: Record<string, string> }>("/settings", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function reEvaluateAll() {
  return api<import("../types").ReEvaluateResult>("/jobs/re-evaluate-all", { method: "POST" });
}

export async function runCollectors() {
  return api<import("../types").CollectorRun>("/collectors/run", { method: "POST" });
}

export async function listCollectorRuns(limit = 5) {
  return api<import("../types").CollectorRun[]>(`/collectors/runs?limit=${limit}`);
}

export async function listDiscoveredJobs(params: Record<string, unknown> = {}) {
  return api<import("../types").DiscoveredJobList>(`/discovered-jobs${buildQuery(params)}`);
}

export async function getDiscoveredJob(id: number) {
  return api<import("../types").DiscoveredJob>(`/discovered-jobs/${id}`);
}

export async function patchDiscoveredJob(id: number, payload: { status: string }) {
  return api<import("../types").DiscoveredJob>(`/discovered-jobs/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function extractDiscoveredJob(id: number) {
  return api<import("../types").ExtractionPreview>(`/discovered-jobs/${id}/extract`, {
    method: "POST",
  });
}

export async function linkDiscoveredJob(discoveredId: number, jobId: number) {
  return api<import("../types").DiscoveredJob>(`/discovered-jobs/${discoveredId}/link-imported-job`, {
    method: "POST",
    body: JSON.stringify({ job_id: jobId }),
  });
}
