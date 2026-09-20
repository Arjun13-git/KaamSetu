// Errors from the API (or from reaching it), reduced to plain data that Server Actions can return
// to client components. Nothing here reads configuration or secrets.

export interface FieldProblem {
  path: string;
  message: string;
}

export interface ApiFailure {
  code: string;
  message: string;
  status: number;
  requestId: string | null;
  fields: FieldProblem[];
}

export type Result<T> = { ok: true; data: T } | { ok: false; error: ApiFailure };

export class ApiError extends Error {
  failure: ApiFailure;

  constructor(failure: ApiFailure) {
    super(failure.message);
    this.name = "ApiError";
    this.failure = failure;
  }
}

/** Server-side "the request never produced an API answer" codes. */
export const NETWORK = "NETWORK_ERROR";
export const TIMEOUT = "TIMEOUT";

export function failureFromBody(status: number, body: unknown, requestId: string | null): ApiFailure {
  const error =
    body && typeof body === "object" && "error" in body
      ? ((body as { error?: unknown }).error as Record<string, unknown> | undefined)
      : undefined;
  const details = (error?.details ?? {}) as { fields?: unknown };
  const fields: FieldProblem[] = Array.isArray(details.fields)
    ? details.fields.flatMap((entry: unknown) => {
        if (!entry || typeof entry !== "object") return [];
        const { loc, message } = entry as { loc?: unknown; message?: unknown };
        const path = Array.isArray(loc) ? loc.filter((part) => part !== "body").join(".") : "";
        return [{ path, message: typeof message === "string" ? message : "Invalid value" }];
      })
    : [];
  return {
    code: typeof error?.code === "string" ? error.code : `HTTP_${status}`,
    message: typeof error?.message === "string" ? error.message : `The API answered ${status}`,
    status,
    requestId:
      requestId ??
      (body && typeof body === "object" && typeof (body as { request_id?: unknown }).request_id === "string"
        ? (body as { request_id: string }).request_id
        : null),
    fields,
  };
}

export const CONFIG = "CONFIG_ERROR";

export function toFailure(error: unknown): ApiFailure {
  if (error instanceof ApiError) return error.failure;
  // Server configuration problems name the missing setting (never its value), so they are safe to show.
  if (error instanceof Error && error.name === "ConfigError") {
    return { code: CONFIG, message: error.message, status: 500, requestId: null, fields: [] };
  }
  const message = error instanceof Error ? error.message : "Something went wrong";
  return { code: "INTERNAL_ERROR", message, status: 500, requestId: null, fields: [] };
}

/** Plain-language text for a failure, safe to show to a person operating the app. */
export function friendlyMessage(failure: ApiFailure): string {
  switch (failure.code) {
    case NETWORK:
      return "KaamSetu could not reach the service. Check the connection and try again.";
    case CONFIG:
      return "This app is not set up to reach the KaamSetu service. Check the server configuration (API address and key).";
    case TIMEOUT:
      return "The service took too long to answer. Nothing was lost; try again.";
    case "UNAUTHORIZED":
    case "FORBIDDEN":
      return "The service rejected this app's credentials. Check the server configuration.";
    case "NOT_FOUND":
      return "That record no longer exists.";
    case "CONFLICT":
    case "INVALID_STATE_TRANSITION":
      return failure.message || "This job changed in the meantime. It has been refreshed.";
    case "DUPLICATE_REQUEST":
      return "That request key was already used for a different message. Send it again as new.";
    case "AI_UNAVAILABLE":
    case "AI_INVALID_OUTPUT":
      return "The AI could not read this message. The request was saved for a person to review.";
    case "VALIDATION_ERROR":
      return failure.fields.length > 0
        ? failure.fields.map((f) => (f.path ? `${f.path}: ${f.message}` : f.message)).join(" · ")
        : failure.message;
    default:
      return failure.status >= 500
        ? "The service had a problem. Nothing was lost; try again in a moment."
        : failure.message;
  }
}

/** Await a read and get a value back either way, so a page can render the failure inline. */
export async function attempt<T>(work: Promise<T>): Promise<Result<T>> {
  try {
    return { ok: true, data: await work };
  } catch (error) {
    return { ok: false, error: toFailure(error) };
  }
}
