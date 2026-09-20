// Pure formatting helpers. Every function takes the timezone (and, where it matters, "now") as an
// argument, so results are the same on the server and in tests. They never touch the environment.

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

export function localDate(iso: string | Date, tz: string): string {
  // en-CA formats as YYYY-MM-DD
  return new Intl.DateTimeFormat("en-CA", { timeZone: tz, year: "numeric", month: "2-digit", day: "2-digit" }).format(
    new Date(iso),
  );
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

/** Calendar parts of an instant in `tz`. Month and weekday names are fixed, not ICU-dependent. */
function calendar(instant: string | Date, tz: string) {
  const [year, month, day] = localDate(instant, tz).split("-").map(Number);
  const weekday = WEEKDAYS[new Date(Date.UTC(year, month - 1, day)).getUTCDay()];
  return { year, day, month: MONTHS[month - 1], weekday };
}

export function formatDate(iso: string, tz: string): string {
  const c = calendar(iso, tz);
  return `${c.day} ${c.month} ${c.year}`;
}

export function formatDayMonth(iso: string, tz: string): string {
  const c = calendar(iso, tz);
  return `${c.day} ${c.month}`;
}

export function formatTime(iso: string, tz: string): string {
  return new Intl.DateTimeFormat("en-IN", { timeZone: tz, hour: "numeric", minute: "2-digit", hour12: true })
    .format(new Date(iso))
    .replace(/\s?([ap])m/i, (_, half: string) => ` ${half.toLowerCase()}m`);
}

export function formatDateTime(iso: string, tz: string): string {
  return `${formatDayMonth(iso, tz)}, ${formatTime(iso, tz)}`;
}

/** "Today", "Tomorrow" or a short date, relative to `now` in the business timezone. */
export function dayWord(iso: string, tz: string, now: Date): string {
  const target = Date.parse(`${localDate(iso, tz)}T00:00:00Z`);
  const today = Date.parse(`${localDate(now, tz)}T00:00:00Z`);
  const days = Math.round((target - today) / DAY);
  if (days === 0) return "Today";
  if (days === 1) return "Tomorrow";
  if (days === -1) return "Yesterday";
  const c = calendar(iso, tz);
  return `${c.weekday} ${c.day} ${c.month}`;
}

export function formatSlot(slot: { start: string; end?: string | null } | null, tz: string, now: Date): string | null {
  if (!slot) return null;
  const head = `${dayWord(slot.start, tz, now)}, ${formatTime(slot.start, tz)}`;
  return slot.end ? `${head} – ${formatTime(slot.end, tz)}` : head;
}

/** A compact age: "just now", "12 min ago", "3 h ago", "yesterday", "45 days ago", "7 months ago". */
export function relativeTime(iso: string, now: Date): string {
  const diff = now.getTime() - Date.parse(iso);
  if (diff < 0) return "upcoming";
  if (diff < MINUTE) return "just now";
  if (diff < HOUR) return `${Math.floor(diff / MINUTE)} min ago`;
  if (diff < DAY) return `${Math.floor(diff / HOUR)} h ago`;
  const days = Math.floor(diff / DAY);
  if (days === 1) return "yesterday";
  if (days < 60) return `${days} days ago`;
  if (days < 365) return `${Math.round(days / 30)} months ago`;
  return `${Math.round(days / 365)} y ago`;
}

/**
 * The model reads "tomorrow, after 5" as a date and a time in the business's own clock
 * (`2026-09-21`, `17:00:00`). This turns that pair into words without guessing what is missing.
 */
export function describeTimePreference(
  pref: { date: string | null; start: string | null; end: string | null },
  tz: string,
  now: Date,
): string | null {
  if (!pref.date && !pref.start) return null;
  const parts: string[] = [];
  if (pref.date) {
    const noon = `${pref.date}T12:00:00Z`;
    const target = Date.parse(`${pref.date}T00:00:00Z`);
    const today = Date.parse(`${localDate(now, tz)}T00:00:00Z`);
    const days = Math.round((target - today) / DAY);
    parts.push(
      days === 0
        ? "Today"
        : days === 1
          ? "Tomorrow"
          : (() => {
              const c = calendar(noon, "UTC");
              return `${c.weekday} ${c.day} ${c.month}`;
            })(),
    );
  }
  const clock = (value: string | null) => {
    if (!value) return null;
    const [h, m] = value.split(":").map(Number);
    if (Number.isNaN(h)) return null;
    const suffix = h >= 12 ? "pm" : "am";
    return `${h % 12 || 12}:${String(m ?? 0).padStart(2, "0")} ${suffix}`;
  };
  const start = clock(pref.start);
  const end = clock(pref.end);
  if (start && end) parts.push(`${start} – ${end}`);
  else if (start) parts.push(`from ${start}`);
  return parts.join(", ");
}

/**
 * A wall-clock value from a `datetime-local` input ("2026-09-21T17:00"), read in `tz`, as a UTC
 * instant. Used to schedule a job in the business's own timezone regardless of the server's.
 */
export function zonedToUtc(local: string, tz: string): string | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(local);
  if (!match) return null;
  const [y, mo, d, h, mi] = match.slice(1).map(Number);
  const guess = Date.UTC(y, mo - 1, d, h, mi);
  const offsetAt = (instant: number) => {
    const parts = new Intl.DateTimeFormat("en-US", {
      timeZone: tz,
      hourCycle: "h23",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    }).formatToParts(new Date(instant));
    const get = (type: string) => Number(parts.find((p) => p.type === type)?.value);
    return Date.UTC(get("year"), get("month") - 1, get("day"), get("hour"), get("minute")) - instant;
  };
  const first = guess - offsetAt(guess);
  const utc = guess - offsetAt(first);
  return new Date(utc).toISOString();
}

/** The reverse: a UTC instant as a `datetime-local` value in `tz`. */
export function utcToZonedInput(iso: string, tz: string): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: tz,
    hourCycle: "h23",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).formatToParts(new Date(iso));
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "00";
  return `${get("year")}-${get("month")}-${get("day")}T${get("hour")}:${get("minute")}`;
}

const ASSET_LABELS: Record<string, string> = {
  air_conditioner: "air conditioner",
  refrigerator: "refrigerator",
  washing_machine: "washing machine",
  microwave: "microwave",
  television: "television",
  water_purifier: "water purifier",
  computer: "computer",
  printer: "printer",
  electrical: "electrical work",
  plumbing: "plumbing",
  other: "appliance",
  unknown: "appliance",
};

export function assetTypeLabel(type: string): string {
  return ASSET_LABELS[type] ?? type.replace(/_/g, " ");
}

/** "LG air conditioner" (brand when known), never an invented model. */
export function applianceLabel(asset: { asset_type: string; brand: string | null }): string {
  const type = assetTypeLabel(asset.asset_type);
  return asset.brand ? `${asset.brand} ${type}` : type;
}

export function sentenceCase(text: string): string {
  const spaced = text.replace(/_/g, " ").trim();
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

/** "+919000020001" -> "+91 90000 20001". Anything unexpected is returned unchanged. */
export function formatPhone(phone: string | null): string | null {
  if (!phone) return null;
  const match = /^\+91(\d{5})(\d{5})$/.exec(phone);
  return match ? `+91 ${match[1]} ${match[2]}` : phone;
}

export function plural(count: number, one: string, many = `${one}s`): string {
  return `${count} ${count === 1 ? one : many}`;
}
