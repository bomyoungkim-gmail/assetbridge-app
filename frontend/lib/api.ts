// Cliente fino dos endpoints HITL do AssetBridge (ADR-0009).
// Nenhuma regra de identidade vive aqui — só transporte. O contrato é o do
// backend (`hitl.router`): GET /pending e POST /pending/{id}/decision.

// Dois contextos de execução, resolvidos por bundle (typeof window):
// - Server Components (listarPendencias): roda no container → rede interna do
//   compose via ASSETBRIDGE_API_URL (http://api:8000).
// - Client Components (decidirPendencia no browser): porta publicada no host
//   via NEXT_PUBLIC_ASSETBRIDGE_API_URL (http://localhost:8001).
const API_URL =
  typeof window === "undefined"
    ? process.env.ASSETBRIDGE_API_URL ?? "http://localhost:8001"
    : process.env.NEXT_PUBLIC_ASSETBRIDGE_API_URL ?? "http://localhost:8001";

// Espelha PendingResolution exposto por GET /pending.
export interface Pendencia {
  id: number;
  chave_provisoria: string;
  motivo: string;
  payload: Record<string, unknown>;
}

// Campos fortes que o operador confirma ao decidir (AssetIdentity do backend).
export interface DecisaoIdentidade {
  tipo: string;
  data_vencimento: string;
  isin?: string | null;
  cnpj_emissor?: string | null;
  serie_emissao?: string | null;
  is_subordinado?: boolean;
}

export interface ResultadoDecisao {
  iup: string;
  rotulo_semantico?: string;
  novo: boolean;
  status: string;
}

export async function listarPendencias(): Promise<Pendencia[]> {
  const res = await fetch(`${API_URL}/pending`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Falha ao listar pendências: HTTP ${res.status}`);
  }
  const data = (await res.json()) as { pending: Pendencia[] };
  return data.pending;
}

export async function decidirPendencia(
  pendingId: number,
  identidade: DecisaoIdentidade,
): Promise<ResultadoDecisao> {
  const res = await fetch(`${API_URL}/pending/${pendingId}/decision`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(identidade),
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Falha ao decidir pendência ${pendingId}: HTTP ${res.status}`);
  }
  return (await res.json()) as ResultadoDecisao;
}

// --- Fontes de enriquecimento (ADR-0011): registry CRUD ---
// Espelha SourceConfig exposto por GET /sources. `vivo` = liga no grafo agora
// (só `tipo='api'` habilitada); csv/scraping ficam catalogados/deferidos.
export interface Fonte {
  id: number;
  nome: string;
  tipo: string;
  base_url: string | null;
  path: string | null;
  param: string;
  field_map: Record<string, string> | null;
  confianca: number;
  enabled: boolean;
  vivo: boolean;
}

export interface NovaFonte {
  nome: string;
  tipo: string;
  base_url?: string | null;
  path?: string | null;
  param?: string;
  field_map?: Record<string, string> | null;
  confianca?: number;
}

export async function listarFontes(): Promise<Fonte[]> {
  const res = await fetch(`${API_URL}/sources`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Falha ao listar fontes: HTTP ${res.status}`);
  }
  const data = (await res.json()) as { sources: Fonte[] };
  return data.sources;
}

export async function criarFonte(fonte: NovaFonte): Promise<Fonte> {
  const res = await fetch(`${API_URL}/sources`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(fonte),
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Falha ao cadastrar fonte: HTTP ${res.status}`);
  }
  return (await res.json()) as Fonte;
}

export async function alterarFonte(id: number, enabled: boolean): Promise<Fonte> {
  const res = await fetch(`${API_URL}/sources/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled }),
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Falha ao alterar fonte ${id}: HTTP ${res.status}`);
  }
  return (await res.json()) as Fonte;
}

export async function removerFonte(id: number): Promise<void> {
  const res = await fetch(`${API_URL}/sources/${id}`, {
    method: "DELETE",
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Falha ao remover fonte ${id}: HTTP ${res.status}`);
  }
}

// --- Acervo (item 4 / browse): superfícies read-only do que foi injetado ---

export interface Ativo {
  id: number;
  iup: string;
  chave_sintetica: string | null;
  created_at: string | null;
}

export interface Posicao {
  id: number;
  id_carteira: string;
  custodiante: string;
  iup: string | null;
  asof: string | null;
  quantidade: string | null;
  pu: string | null;
}

export interface Import {
  id: number;
  custodiante: string;
  content_hash: string;
  tamanho_bytes: number;
  created_at: string | null;
}

// Espelha a resposta de POST /ingest (api.ingest_btg): bruto vai pra landing
// zone (no-op se `duplicate`), posições roteadas (chave forte → IUP; fraca →
// HITL; sintética → exclusão) e projetadas. Contadores do ciclo + parse bruto.
export interface ResultadoIngest {
  source: string;
  file_name: string | null;
  status: "ingested" | "duplicate";
  id_carteira: string;
  asof: string;
  posicoes: number;
  pendencias: number;
  excluidos: number;
  parsed: unknown;
}

// Upload de XML BTG: o endpoint lê o corpo cru (request.body()), então o File
// vai direto como body; o nome viaja no header X-File-Name. Client-only.
export async function enviarIngest(file: File): Promise<ResultadoIngest> {
  const res = await fetch(`${API_URL}/ingest`, {
    method: "POST",
    headers: { "X-File-Name": file.name },
    body: file,
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Falha ao enviar ${file.name}: HTTP ${res.status}`);
  }
  return (await res.json()) as ResultadoIngest;
}

async function getJson<T>(path: string, key: string): Promise<{ total: number; itens: T[] }> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Falha ao listar ${path}: HTTP ${res.status}`);
  }
  const data = (await res.json()) as Record<string, unknown>;
  return { total: data.total as number, itens: (data[key] as T[]) ?? [] };
}

export function listarAtivos() {
  return getJson<Ativo>("/assets", "assets");
}

export function listarPosicoes() {
  return getJson<Posicao>("/positions", "positions");
}

export function listarImports() {
  return getJson<Import>("/imports", "imports");
}
