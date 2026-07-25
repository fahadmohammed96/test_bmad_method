import { render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const replaceMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceMock, push: vi.fn() }),
}));

const useMeMock = vi.fn();
vi.mock("@/lib/api/hooks", () => ({
  useMe: () => useMeMock(),
}));

import Home from "../page";

describe("Home (smistatore)", () => {
  beforeEach(() => {
    replaceMock.mockClear();
  });

  it("Host autenticato → Dashboard", async () => {
    useMeMock.mockReturnValue({
      data: { id: "x", email: "host@example.com" },
      isPending: false,
      isError: false,
    });
    render(<Home />);
    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/dashboard"));
  });

  it("non autenticato → Accesso", async () => {
    useMeMock.mockReturnValue({ data: null, isPending: false, isError: false });
    render(<Home />);
    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/accesso"));
  });
});
