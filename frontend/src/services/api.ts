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
