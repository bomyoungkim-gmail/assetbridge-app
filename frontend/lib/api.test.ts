import { describe, it, expect, vi, afterEach } from "vitest";
import {
  listarPendencias,
  decidirPendencia,
  listarFontes,
  criarFonte,
  removerFonte,
  listarPosicoes,
  enviarIngest,
} from "@/lib/api";

afterEach(() => vi.restoreAllMocks());

describe("listarPendencias", () => {
  it("retorna a lista de pendências do backend", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        pending: [
          {
            id: 1,
            chave_provisoria: "sint_abc",
            motivo: "sem chave forte",
            payload: {},
          },
        ],
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const r = await listarPendencias();

    expect(r).toHaveLength(1);
    expect(r[0].id).toBe(1);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/pending"),
      expect.anything(),
    );
  });

  it("lança em HTTP não-ok", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 500 }));
    await expect(listarPendencias()).rejects.toThrow(/HTTP 500/);
  });
});

describe("decidirPendencia", () => {
  it("faz POST com a identidade e devolve o resultado", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ iup: "IUP-abc", novo: true, status: "resolved" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const r = await decidirPendencia(7, {
      tipo: "CDB",
      data_vencimento: "2030-01-01",
    });

    expect(r.iup).toBe("IUP-abc");
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain("/pending/7/decision");
    expect(opts.method).toBe("POST");
    expect(JSON.parse(opts.body).tipo).toBe("CDB");
  });

  it("lança em HTTP não-ok", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 422 }));
    await expect(
      decidirPendencia(1, { tipo: "", data_vencimento: "" }),
    ).rejects.toThrow(/HTTP 422/);
  });
});

describe("fontes (registry ADR-0011)", () => {
  it("lista fontes do backend", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          sources: [{ id: 1, nome: "CVM", tipo: "api", vivo: true }],
        }),
      }),
    );
    const r = await listarFontes();
    expect(r).toHaveLength(1);
    expect(r[0].nome).toBe("CVM");
  });

  it("cadastra fonte via POST", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 9, nome: "B3", tipo: "api", enabled: true }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const r = await criarFonte({ nome: "B3", tipo: "api", base_url: "http://x" });
    expect(r.id).toBe(9);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain("/sources");
    expect(opts.method).toBe("POST");
    expect(JSON.parse(opts.body).nome).toBe("B3");
  });

  it("remove fonte via DELETE", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    await removerFonte(3);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain("/sources/3");
    expect(opts.method).toBe("DELETE");
  });

  it("lança em HTTP não-ok ao listar", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 500 }));
    await expect(listarFontes()).rejects.toThrow(/HTTP 500/);
  });
});

describe("enviarIngest", () => {
  it("faz POST do XML bruto com X-File-Name e devolve o parse", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        source: "btg_position_xml",
        file_name: "pos.xml",
        parsed: { fundo: "X" },
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const file = new File(["<xml/>"], "pos.xml", { type: "text/xml" });
    const r = await enviarIngest(file);

    expect(r.source).toBe("btg_position_xml");
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain("/ingest");
    expect(opts.method).toBe("POST");
    expect(opts.body).toBe(file);
    expect(opts.headers["X-File-Name"]).toBe("pos.xml");
  });

  it("lança em HTTP não-ok", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 400 }));
    const file = new File(["<xml/>"], "pos.xml", { type: "text/xml" });
    await expect(enviarIngest(file)).rejects.toThrow(/HTTP 400/);
  });
});

describe("acervo (browse)", () => {
  it("lista posições e expõe o total", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          total: 1,
          positions: [
            { id: 1, id_carteira: "C1", custodiante: "BTG", quantidade: "1000" },
          ],
        }),
      }),
    );
    const r = await listarPosicoes();
    expect(r.total).toBe(1);
    expect(r.itens[0].id_carteira).toBe("C1");
  });
});
