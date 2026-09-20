import "server-only";

export interface WebConfig {
  apiUrl: string;
  demoKey: string | null;
  timezone: string;
}

export class ConfigError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ConfigError";
  }
}

const DEFAULT_TIMEZONE = "Asia/Kolkata";

/**
 * Server-only settings. None of these variables is prefixed NEXT_PUBLIC_, so Next.js never inlines
 * them into browser code, and this module refuses to be imported from a client component.
 */
export function getConfig(): WebConfig {
  const raw = process.env.KAAMSETU_API_URL?.trim();
  if (!raw) {
    throw new ConfigError("KAAMSETU_API_URL is not set. Copy apps/web/.env.example to .env.local.");
  }
  return {
    apiUrl: raw.replace(/\/+$/, ""),
    demoKey: process.env.KAAMSETU_DEMO_KEY?.trim() || null,
    timezone: process.env.KAAMSETU_TIMEZONE?.trim() || DEFAULT_TIMEZONE,
  };
}

export function getTimezone(): string {
  return process.env.KAAMSETU_TIMEZONE?.trim() || DEFAULT_TIMEZONE;
}
