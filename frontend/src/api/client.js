import axios from "axios";

// Empty base URL means relative requests (/api/...), which the Vite dev proxy forwards to Django.
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 8000,
  headers: { Accept: "application/json" },
});

export function connectionMode() {
  return API_BASE_URL ? `Direct to ${API_BASE_URL} (CORS)` : "Through the Vite proxy";
}

/** Turn any Axios failure into { code, message } the UI can show. */
export function toApiError(err) {
  const body = err?.response?.data;
  if (body?.status === "error" && body.error) {
    return { code: body.error.code, message: body.error.message };
  }
  if (err?.response) {
    return {
      code: `http_${err.response.status}`,
      message: `Got HTTP ${err.response.status} instead of an API response. Check that Django is running on port 8000.`,
    };
  }
  if (err?.code === "ECONNABORTED") {
    return { code: "timeout", message: "The backend took too long to answer." };
  }
  return {
    code: "network_error",
    message: "Can't reach the backend. Start Django with: python manage.py runserver",
  };
}
