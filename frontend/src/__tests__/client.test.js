import { describe, expect, it } from "vitest";
import { toApiError } from "../api/client.js";

describe("toApiError", () => {
  it("uses the backend's error envelope when present", () => {
    const err = {
      response: { status: 503, data: { status: "error", error: { code: "service_unavailable", message: "DB down" } } },
    };
    expect(toApiError(err)).toEqual({ code: "service_unavailable", message: "DB down" });
  });

  it("explains a non-API response, e.g. the Vite proxy failing", () => {
    expect(toApiError({ response: { status: 502, data: "" } }).code).toBe("http_502");
  });

  it("reports timeouts", () => {
    expect(toApiError({ code: "ECONNABORTED" }).code).toBe("timeout");
  });

  it("falls back to a network error", () => {
    expect(toApiError(new Error("boom")).code).toBe("network_error");
  });
});
