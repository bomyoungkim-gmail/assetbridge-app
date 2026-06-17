import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Resolver from "@/app/hitl/resolver";
import { decidirPendencia } from "@/lib/api";

const refresh = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh }) }));
vi.mock("@/lib/api", () => ({ decidirPendencia: vi.fn() }));

beforeEach(() => vi.clearAllMocks());

describe("Resolver", () => {
  it("abre o formulário ao clicar em Resolver", async () => {
    render(<Resolver pendingId={3} />);
    await userEvent.click(screen.getByRole("button", { name: "Resolver" }));
    expect(screen.getByPlaceholderText("CDB / CRI / LF")).toBeInTheDocument();
  });

  it("cunha o IUP com a identidade e recarrega a fila ao submeter", async () => {
    (decidirPendencia as ReturnType<typeof vi.fn>).mockResolvedValue({
      iup: "IUP-x",
      novo: true,
      status: "resolved",
    });
    render(<Resolver pendingId={3} />);

    await userEvent.click(screen.getByRole("button", { name: "Resolver" }));
    await userEvent.type(screen.getByPlaceholderText("CDB / CRI / LF"), "CDB");
    await userEvent.click(screen.getByRole("button", { name: "Cunhar IUP" }));

    expect(decidirPendencia).toHaveBeenCalledWith(
      3,
      expect.objectContaining({ tipo: "CDB" }),
    );
    expect(refresh).toHaveBeenCalled();
  });
});
