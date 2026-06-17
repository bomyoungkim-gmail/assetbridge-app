import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Uploader from "@/app/acervo/uploader";
import { enviarIngest } from "@/lib/api";

const refresh = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh }) }));
vi.mock("@/lib/api", () => ({ enviarIngest: vi.fn() }));

beforeEach(() => vi.clearAllMocks());

describe("Uploader", () => {
  it("envia o arquivo escolhido e recarrega o acervo", async () => {
    (enviarIngest as ReturnType<typeof vi.fn>).mockResolvedValue({
      source: "btg_position_xml",
      file_name: "pos.xml",
      status: "ingested",
      id_carteira: "55064365000171",
      asof: "2026-06-03",
      posicoes: 1,
      pendencias: 0,
      excluidos: 0,
      parsed: {},
    });
    render(<Uploader />);

    const file = new File(["<xml/>"], "pos.xml", { type: "text/xml" });
    await userEvent.upload(screen.getByLabelText(/XML BTG/i), file);
    await userEvent.click(screen.getByRole("button", { name: "Enviar" }));

    expect(enviarIngest).toHaveBeenCalledWith(file);
    expect(refresh).toHaveBeenCalled();
    expect(await screen.findByText(/1 posição/)).toBeInTheDocument();
  });

  it("não envia sem arquivo selecionado", async () => {
    render(<Uploader />);
    await userEvent.click(screen.getByRole("button", { name: "Enviar" }));
    expect(enviarIngest).not.toHaveBeenCalled();
  });

  it("mostra erro quando o ingest falha", async () => {
    (enviarIngest as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error("HTTP 400"),
    );
    render(<Uploader />);

    const file = new File(["<xml/>"], "pos.xml", { type: "text/xml" });
    await userEvent.upload(screen.getByLabelText(/XML BTG/i), file);
    await userEvent.click(screen.getByRole("button", { name: "Enviar" }));

    expect(await screen.findByText(/HTTP 400/)).toBeInTheDocument();
    expect(refresh).not.toHaveBeenCalled();
  });
});
