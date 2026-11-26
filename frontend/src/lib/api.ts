import type {
  AiAdvice,
  ExampleRepo,
  Health,
  Report,
  ReportSummary,
  ScanJob,
  ScanStart,
  UpdateCheck,
} from "./types";

export class ApiError extends Error {
  code: string;
  status: number;
  retryAfter: number | null;

  constructor(
    message: string,
    options: { code?: string; status?: number; retryAfter?: number | null } = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.code = options.code || "REQUEST_FAILED";
    this.status = options.status || 0;
    this.retryAfter = options.retryAfter ?? null;
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  timeoutMs = 30_000,
): Promise<T> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const headers = new Headers(init.headers || {});
    if (init.body && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    const response = await fetch(path, {
      ...init,
      headers,
      signal: controller.signal,
    });
    const text = await response.text();
    let payload: unknown = null;
    if (text) {
      try {
        payload = JSON.parse(text);
      } catch {
        payload = text;
      }
    }
    if (!response.ok) {
      const obj = (payload || {}) as Record<string, unknown>;
      throw new ApiError(
        String(obj.message || `请求失败（HTTP ${response.status}）`),
        {
          code: String(obj.error_code || "REQUEST_FAILED"),
          status: response.status,
          retryAfter:
            typeof obj.retry_after === "number" ? obj.retry_after : null,
        },
      );
    }
    return payload as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("请求超时，请稍后重试", { code: "TIMEOUT" });
    }
    throw new ApiError("无法连接服务，请确认后端已启动", {
      code: "NETWORK_ERROR",
    });
  } finally {
    window.clearTimeout(timer);
  }
}

export const api = {
  health: () => request<Health>("/api/health"),
  examples: () => request<ExampleRepo[]>("/api/examples"),
  recent: (limit = 8) =>
    request<ReportSummary[]>(`/api/reports?limit=${limit}`),
  startScan: (url: string, force = false) =>
    request<ScanStart>("/api/scans", {
      method: "POST",
      body: JSON.stringify({ url, force }),
    }),
  getJob: (jobId: string) =>
    request<ScanJob>(`/api/scans/${encodeURIComponent(jobId)}`),
  getReport: (reportId: string) =>
    request<Report>(`/api/reports/${encodeURIComponent(reportId)}`),
  refresh: (reportId: string) =>
    request<ScanStart>(
      `/api/reports/${encodeURIComponent(reportId)}/refresh`,
      { method: "POST" },
    ),
  checkUpdates: (reportId: string) =>
    request<UpdateCheck>(
      `/api/reports/${encodeURIComponent(reportId)}/updates`,
    ),
  generateAi: (reportId: string) =>
    request<AiAdvice>(
      `/api/reports/${encodeURIComponent(reportId)}/ai`,
      { method: "POST" },
      65_000,
    ),
  exportUrl: (reportId: string, format: "json" | "md") =>
    `/api/reports/${encodeURIComponent(reportId)}/export?format=${format}`,
};

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.retryAfter && error.status === 429) {
      return `${error.message}（约 ${error.retryAfter}s 后重试）`;
    }
    return error.message;
  }
  if (error instanceof Error) return error.message;
  return "未知错误";
}
