import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, createTeamMember, listTeam, resendTeamInvitation } from "./api";

beforeEach(() => {
  document.cookie = "csrftoken=test-csrf";
  vi.restoreAllMocks();
});

describe("listTeam", () => {
  it("composes URL /api/v1/team/ with search param", async () => {
    const mock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () =>
        Promise.resolve({
          count: 0,
          next: null,
          previous: null,
          results: [],
        }),
    });
    vi.stubGlobal("fetch", mock);
    await listTeam({ search: "alice", region_id: 3 });
    const url = mock.mock.calls[0][0] as string;
    expect(url).toContain("/api/v1/team/");
    expect(url).toContain("search=alice");
    expect(url).toContain("region_id=3");
  });

  it("throws ApiError on non-2xx response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 403,
        json: () => Promise.resolve({ detail: "forbidden" }),
      }),
    );
    await expect(listTeam()).rejects.toBeInstanceOf(ApiError);
  });
});

describe("createTeamMember", () => {
  it("sends POST with JSON body and X-CSRFToken header", async () => {
    const mock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: () =>
        Promise.resolve({
          id: 1,
          full_name: "Alice",
          email: "alice@example.com",
          role: "STAFF_ADMIN",
          is_active: false,
          invited_at: null,
          accepted_at: null,
          status: "PENDING",
          access_scopes: [],
        }),
    });
    vi.stubGlobal("fetch", mock);
    await createTeamMember({
      full_name: "Alice",
      email: "alice@example.com",
      invited_for_role: "STAFF_ADMIN",
    });
    const [url, init] = mock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/team/");
    expect((init.headers as Record<string, string>)["X-CSRFToken"]).toBe("test-csrf");
    const body = JSON.parse(init.body as string) as Record<string, unknown>;
    expect(body.email).toBe("alice@example.com");
  });
});

describe("resendTeamInvitation", () => {
  it("sends POST to /api/v1/team/{id}/resend/", async () => {
    const mock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () =>
        Promise.resolve({
          id: 7,
          full_name: "Bob",
          email: "bob@example.com",
          role: "STAFF_ADMIN",
          is_active: false,
          invited_at: "2026-01-01T00:00:00Z",
          accepted_at: null,
          status: "PENDING",
          access_scopes: [],
        }),
    });
    vi.stubGlobal("fetch", mock);
    await resendTeamInvitation(7);
    const [url, init] = mock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/team/7/resend/");
    expect(init.method).toBe("POST");
  });
});
