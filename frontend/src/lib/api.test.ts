import { describe, expect, it } from "vitest";
import { AxiosError, AxiosHeaders } from "axios";
import { apiError } from "./api";

function axiosErr(data: unknown, code?: string): AxiosError {
  const err = new AxiosError("boom", code);
  // @ts-expect-error minimal response shape for the test
  err.response = data === undefined ? undefined : { data, status: 400, headers: new AxiosHeaders() };
  return err;
}

describe("apiError", () => {
  it("returns a string FastAPI detail directly", () => {
    expect(apiError(axiosErr({ detail: "Incorrect email or password." }))).toBe(
      "Incorrect email or password."
    );
  });

  it("flattens a Pydantic 422 detail array with field names", () => {
    const msg = apiError(
      axiosErr({
        detail: [
          { loc: ["body", "trestbps"], msg: "input should be less than 260" },
          { loc: ["body", "age"], msg: "field required" },
        ],
      })
    );
    expect(msg).toContain("trestbps");
    expect(msg).toContain("age");
  });

  it("gives a friendly message on network failure", () => {
    expect(apiError(axiosErr(undefined, "ERR_NETWORK"))).toMatch(/cannot reach the server/i);
  });

  it("falls back for unknown errors", () => {
    expect(apiError(new Error("nope"))).toMatch(/something went wrong/i);
  });
});
