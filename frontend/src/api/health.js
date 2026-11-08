import { api, toApiError } from "./client.js";

export async function fetchHealth() {
  const started = performance.now();
  try {
    const { data } = await api.get("/api/health/");
    if (data?.status !== "ok") {
      throw { response: { status: 200, data } };
    }
    return { ...data.data, latencyMs: Math.round(performance.now() - started) };
  } catch (err) {
    throw toApiError(err);
  }
}
