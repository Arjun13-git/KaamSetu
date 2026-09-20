import { api } from "@/lib/api/endpoints";

export const dynamic = "force-dynamic";

export default async function Home() {
  const health = await api.health();
  return (
    <main className="p-10">
      <h1 className="text-2xl font-semibold tracking-tight">KaamSetu</h1>
      <p className="mt-1 text-ink-2">API {health.status} · v{health.version}</p>
    </main>
  );
}
