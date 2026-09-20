// Reads the AI extraction stored on a ServiceRequest. The API types it as a bare object, so it is
// checked here before the UI relies on any field, and the model's habit of writing "unknown" or
// "null" as text is turned back into "not known".

export type Source = "explicit_text" | "image" | "conversation_context" | "retrieved_history" | "inferred" | "unknown";

export interface ExtractionData {
  intent: string;
  serviceType: string;
  customerReference: string | null;
  asset: { type: string; brand: string | null; model: string | null };
  problem: { description: string | null; urgency: string | null; symptoms: string[] };
  timePreference: { date: string | null; start: string | null; end: string | null };
  confidence: { overall: number; asset: number; problem: number; schedule: number };
  missingInformation: string[];
  sources: Record<string, Source>;
}

export interface ParsedExtraction {
  data: ExtractionData;
  modelId: string;
  promptVersion: string;
  safetyConcern: boolean;
  imageSupplied: boolean;
  warnings: string[];
  /** Hand-written fixtures in the demo dataset, not produced by a model. */
  isFixture: boolean;
}

const SOURCES = new Set<string>(["explicit_text", "image", "conversation_context", "retrieved_history", "inferred", "unknown"]);
const UNKNOWN_WORDS = new Set(["", "unknown", "null", "none", "n/a", "na", "not specified", "unspecified", "not provided"]);

/** A value the customer really gave, or null when the model wrote a placeholder. */
export function knownText(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return UNKNOWN_WORDS.has(trimmed.toLowerCase()) ? null : trimmed;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function strings(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((v): v is string => typeof v === "string" && v.trim() !== "") : [];
}

function score(value: unknown): number {
  return typeof value === "number" && value >= 0 && value <= 1 ? value : 0;
}

export function parseExtraction(raw: unknown): ParsedExtraction | null {
  if (!isRecord(raw) || !isRecord(raw.data)) return null;
  const d = raw.data;
  const asset = isRecord(d.asset) ? d.asset : {};
  const problem = isRecord(d.problem) ? d.problem : {};
  const time = isRecord(d.time_preference) ? d.time_preference : {};
  const confidence = isRecord(d.confidence) ? d.confidence : {};
  const sources: Record<string, Source> = {};
  if (isRecord(d.sources)) {
    for (const [field, source] of Object.entries(d.sources)) {
      if (typeof source === "string" && SOURCES.has(source)) sources[field] = source as Source;
    }
  }
  const modelId = typeof raw.model_id === "string" ? raw.model_id : "unknown";
  return {
    data: {
      intent: typeof d.intent === "string" ? d.intent : "unknown",
      serviceType: typeof d.service_type === "string" ? d.service_type : "unknown",
      customerReference: knownText(d.customer_reference),
      asset: {
        type: typeof asset.type === "string" ? asset.type : "unknown",
        brand: knownText(asset.brand),
        model: knownText(asset.model),
      },
      problem: {
        description: knownText(problem.description),
        urgency: knownText(problem.urgency),
        symptoms: strings(problem.symptoms),
      },
      timePreference: {
        date: knownText(time.date),
        start: knownText(time.start),
        end: knownText(time.end),
      },
      confidence: {
        overall: score(confidence.overall),
        asset: score(confidence.asset),
        problem: score(confidence.problem),
        schedule: score(confidence.schedule),
      },
      missingInformation: strings(d.missing_information),
      sources,
    },
    modelId,
    promptVersion: typeof raw.prompt_version === "string" ? raw.prompt_version : "unknown",
    safetyConcern: raw.safety_concern === true,
    imageSupplied: raw.image_supplied === true,
    warnings: strings(raw.warnings),
    isFixture: modelId === "seed-fixture",
  };
}

const MISSING_LABELS: Record<string, string> = {
  "asset.model": "Appliance model",
  "asset.brand": "Appliance brand",
  "asset.type": "Appliance type",
  "problem.description": "What is wrong",
  "problem.urgency": "How urgent it is",
  "problem.symptoms": "Symptoms",
  time_preference: "Preferred time",
  customer_reference: "Who is asking",
};

export function missingLabel(key: string): string {
  return MISSING_LABELS[key] ?? key.replace(/[._]/g, " ").replace(/^./, (c) => c.toUpperCase());
}

export function sourceLabel(source: Source): string {
  switch (source) {
    case "explicit_text":
      return "Stated";
    case "image":
      return "From photo";
    case "conversation_context":
      return "From context";
    case "retrieved_history":
      return "From history";
    case "inferred":
      return "Inferred";
    default:
      return "Unknown";
  }
}

export type ConfidenceBand = "high" | "medium" | "low";

export function confidenceBand(value: number): ConfidenceBand {
  return value >= 0.8 ? "high" : value >= 0.5 ? "medium" : "low";
}
