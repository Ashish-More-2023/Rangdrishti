import { API_BASE_URL, api, toApiError } from "./client.js";

async function get(path) {
  try {
    const { data } = await api.get(path);
    if (data?.status !== "ok") throw { response: { status: 200, data } };
    return data.data;
  } catch (err) {
    throw toApiError(err);
  }
}

export async function fetchShows() {
  return (await get("/api/shows/")).shows;
}

export function fetchResults(slug) {
  return get(`/api/shows/${encodeURIComponent(slug)}/promos/`);
}

export function fetchClip(slug, promoId) {
  return get(`/api/shows/${encodeURIComponent(slug)}/promos/${encodeURIComponent(promoId)}/`);
}

export function csvUrl(slug) {
  return `${API_BASE_URL}/api/shows/${encodeURIComponent(slug)}/promos.csv`;
}
