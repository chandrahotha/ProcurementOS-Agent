import { describe, expect, it } from "vitest";
import { ApiError, verdictTone } from "./api-client";

describe("verdictTone", () => {
  it("maps dry-run verdicts to display tones", () => {
    expect(verdictTone("ALLOW")).toBe("ok");
    expect(verdictTone("NEEDS-APPROVAL")).toBe("warn");
    expect(verdictTone("DENY")).toBe("bad");
    expect(verdictTone("anything-else")).toBe("bad");
  });
});

describe("ApiError", () => {
  it("carries status, code, and request id", () => {
    const e = new ApiError(403, "action_blocked", "blocked", "req_1", { x: 1 });
    expect(e.status).toBe(403);
    expect(e.code).toBe("action_blocked");
    expect(e.requestId).toBe("req_1");
    expect(e.details).toEqual({ x: 1 });
  });
});
