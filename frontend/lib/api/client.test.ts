import { afterEach, describe, expect, it, vi } from "vitest";
import { api, apiBaseUrl } from "./client";

describe("client API generato (AD-14)", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("chiama il backend sotto /api/v1 con il path tipizzato", async () => {
    const fetchMock = vi.fn<typeof fetch>(
      async () =>
        new Response(JSON.stringify({ status: "ok" }), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const { data, error } = await api.GET("/api/v1/health");

    expect(error).toBeUndefined();
    expect(data).toEqual({ status: "ok" });
    const request = fetchMock.mock.calls[0][0] as Request;
    expect(request.url).toBe(`${apiBaseUrl}/api/v1/health`);
  });
});
