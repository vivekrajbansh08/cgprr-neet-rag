// Typed clients for the local services. The UI only displays fields from these responses.

export type Citation = {
  sid: string;
  cell_id: string;
  round: number;
  quota: string;
  institute: string;
  course: string;
  allotted_category: string;
  closing_rank: number | string;
  rank_text: string;
  allotments: number;
  is_cw_nri: boolean;
  file: string;
  source_sha256: string;
  page: number;
  line: number;
};

export type ClarifyOption = { institute_id: number; label: string };

export type AskResponse = {
  answer: string;
  status: "answered" | "refused" | "clarify";
  citations: Citation[];
  sources?: unknown[];
  debug?: unknown;
  clarify_options?: ClarifyOption[];
  guarantee_note?: boolean;
};

export type PredictCell = {
  round: number;
  quota: string;
  course: string;
  category: string;
  closing_rank: string;
  allotments: number;
  file: string;
  page: number;
  line: number;
  source_sha256: string;
};

export type PredictOption = {
  institute: string;
  institute_id: number;
  state: string | null;
  best_closing_rank: string;
  cells: PredictCell[];
  explanation: string;
};

export type BestInScope = {
  institute: string;
  category: string;
  round: number;
  closing_rank: string;
  allotments: number;
  file: string;
  page: number;
  line: number;
  source_sha256: string;
};

export type PredictRequest = {
  rank: number;
  category: string;
  pwd: boolean;
  quota: string;
  course: string;
  round: number;
  state?: string | null;
};

export type PredictResponse = {
  inputs: PredictRequest;
  eligible_categories: string[];
  options: PredictOption[];
  option_count: number;
  institutes_in_scope: number;
  unplaced_no_state: number;
  best_in_scope: BestInScope | null;
  empty_message: string | null;
  note: string;
  source_credit: string;
};

export type FormOptions = {
  categories: string[];
  quotas: string[];
  courses: string[];
  rounds: number[];
  states: string[];
};

export class ApiError extends Error {}

async function request<T>(url: string, init?: RequestInit, timeoutMs = 120_000): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(url, { ...init, signal: ctrl.signal });
    if (!res.ok) {
      let detail = `${res.status} ${res.statusText}`;
      try {
        const body = await res.json();
        if (typeof body?.detail === "string") detail = body.detail;
        else if (Array.isArray(body?.detail) && typeof body.detail[0]?.msg === "string") detail = body.detail[0].msg; // FastAPI 422
      } catch {
        /* not JSON */
      }
      throw new ApiError(detail);
    }
    return (await res.json()) as T;
  } catch (e) {
    if (e instanceof ApiError) throw e;
    if (e instanceof DOMException && e.name === "AbortError") throw new ApiError("The service took too long to reply.");
    throw new ApiError("The service is not reachable on this machine.");
  } finally {
    clearTimeout(timer);
  }
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const ask = (question: string, institute_id?: number) =>
  request<AskResponse>("/api/answer/ask", json(institute_id !== undefined ? { question, institute_id } : { question }));

export const predict = (req: PredictRequest) => request<PredictResponse>("/api/predictor/predict", json(req));

export const formOptions = () => request<FormOptions>("/api/predictor/form_options", undefined, 20_000);

export async function evidence(name: "manifest.md" | "score_table.md"): Promise<string> {
  const res = await fetch(`/evidence/${name}`, { cache: "no-store" });
  if (!res.ok) throw new ApiError(`Could not read ${name} (${res.status}).`);
  return res.text();
}

export const GUARANTEE_SENTENCE =
  "No one can guarantee an allotment; past closing ranks only show what happened in 2025.";

/** First 12 hex characters of a sha256, as printed on every source line. */
export const shortSha = (sha: string) => sha.slice(0, 12);
