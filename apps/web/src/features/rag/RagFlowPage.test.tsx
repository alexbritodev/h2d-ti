import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RagFlowPage } from "./RagFlowPage";

const CHUNK_ID = "11111111-1111-4111-8111-111111111111";
const MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2";

const OVERVIEW = {
  documents: 3,
  chunks: 40,
  avg_words: 48.2,
  max_words: 60,
  public_chunks: 30,
  restricted_chunks: 10,
  params: {
    chunk_max_words: 60,
    model_max_tokens: 128,
    embedding_model: MODEL,
    embedding_dimensions: 384,
    rrf_k: 60,
    candidates: 50,
    search_limit: 5,
    history_messages: 6,
    answer_model: "google/gemma-4-31b-it:free",
    daily_limit: 45,
    calls_today: 12,
  },
};

const embedding = {
  model: MODEL,
  dimensions: 4,
  norm: 1,
  minimum: -0.4,
  maximum: 0.6,
  values: [0.6, -0.4, 0.1, 0.2],
};

const hit = { chunk_id: CHUNK_ID, title: "VPN", breadcrumb: "VPN > Conexão", snippet: "texto" };

const TRACE = {
  question: "Como conecto na VPN?",
  masking: { original_chars: 20, masked_text: "Como conecto na VPN?", redactions: 0, kinds: [] },
  tokenization: {
    model_tokens: [
      { text: "▁Como", id: 1 },
      { text: "▁VP", id: 2 },
      { text: "N", id: 3 },
    ],
    model_token_count: 3,
    model_max_tokens: 128,
    words: [
      { word: "como", lexeme: null },
      { word: "conecto", lexeme: "conect" },
      { word: "vpn", lexeme: "vpn" },
    ],
    tsquery_raw: "como | conecto | vpn",
    tsquery_parsed: "'conect' | 'vpn'",
  },
  embedding,
  vector: [{ ...hit, rank: 1, similarity: 0.81 }],
  lexical: [{ ...hit, rank: 1, score: 0.38 }],
  fusion: [
    {
      ...hit,
      vector_rank: 1,
      lexical_rank: 1,
      vector_part: 0.01639,
      lexical_part: 0.01639,
      score: 0.03278,
      selected: true,
    },
  ],
  rrf_k: 60,
  candidates: 50,
  search_limit: 5,
  prompt: {
    system_prompt: "Regras do sistema",
    sources_block: '<fontes>\n<fonte id="1" titulo="VPN">texto</fonte>\n</fontes>',
    question: "Como conecto na VPN?",
    history_messages: 6,
    sources: [{ ...hit, position: 0, token_count: 140, truncated: true }],
    approx_input_tokens: 300,
  },
  generation: {
    model: "google/gemma-4-31b-it:free",
    fallbacks: ["google/gemma-4-26b-a4b-it:free"],
    temperature: 0.2,
    max_tokens: 700,
    calls_per_turn: "1 a 3",
    daily_limit: 45,
    calls_today: 12,
  },
  timings: [
    { stage: "masking", label: "Mascaramento", ms: 0.1 },
    { stage: "tokenization", label: "Tokenização", ms: 4.2 },
    { stage: "embedding", label: "Embedding", ms: 11.5 },
    { stage: "search", label: "Busca", ms: 8.0 },
    { stage: "fusion", label: "Fusão", ms: 0.3 },
    { stage: "prompt", label: "Prompt", ms: 2.0 },
  ],
  total_ms: 26.1,
};

const CHUNK = {
  chunk_id: CHUNK_ID,
  document_id: "22222222-2222-4222-8222-222222222222",
  title: "VPN corporativa",
  breadcrumb: "VPN > Conexão",
  position: 0,
  visibility: "public",
  content: "Para conectar a VPN, abra o cliente.",
  words: 7,
  tokens: [{ text: "▁Para", id: 9 }],
  token_count: 1,
  model_max_tokens: 128,
  truncated: false,
  lexemes: [{ lexeme: "vpn", count: 1 }],
  embedding,
};

function mockApi() {
  const calls: { path: string; body?: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (request: Request) => {
      const { pathname } = new URL(request.url);
      const json = (body: unknown) =>
        new Response(JSON.stringify(body), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      const body = request.method === "POST" ? await request.clone().json() : undefined;
      calls.push({ path: pathname, body });
      if (pathname === "/api/admin/rag/overview") return json(OVERVIEW);
      if (pathname === "/api/admin/rag/trace") return json(TRACE);
      if (pathname === `/api/admin/rag/chunks/${CHUNK_ID}`) return json(CHUNK);
      return new Response(JSON.stringify({ detail: "não encontrado" }), { status: 404 });
    }),
  );
  return calls;
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <RagFlowPage />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("RagFlowPage", () => {
  it("mostra o resumo da base e explica as etapas de ingestão sem rastreio", async () => {
    mockApi();
    renderPage();

    expect(await screen.findByText("documentos")).toBeTruthy();
    expect(await screen.findByText("12 / 45")).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: /^Trechos/ }));
    expect(await screen.findByText(/trechos de até 60 palavras/)).toBeTruthy();
  });

  it("não deixa rastrear com a pergunta vazia", async () => {
    mockApi();
    renderPage();
    expect(((await screen.findByRole("button", { name: "Rastrear" })) as HTMLButtonElement).disabled).toBe(true);
  });

  it("rastreia a pergunta e mostra cada etapa com dados reais", async () => {
    const calls = mockApi();
    renderPage();
    const user = userEvent.setup();

    await user.type(await screen.findByLabelText("Pergunta de teste"), "Como conecto na VPN?");
    await user.click(screen.getByRole("button", { name: "Rastrear" }));

    expect(await screen.findByText("rastreio de 26,1 ms")).toBeTruthy();
    expect(calls.find((call) => call.path === "/api/admin/rag/trace")?.body).toEqual({
      question: "Como conecto na VPN?",
    });
    // A tokenização é a etapa aberta por padrão: radical, palavra descartada e tokens.
    expect(screen.getByText("conecto → conect")).toBeTruthy();
    expect(screen.getByText("3 de 128 tokens da janela do modelo")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: /^Fusão RRF/ }));
    expect(await screen.findByText("vai ao prompt")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: /^Prompt/ }));
    expect(await screen.findByText("140 tokens · passa da janela")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: /^Modelo/ }));
    expect(await screen.findByText("12 de 45")).toBeTruthy();
  });

  it("abre a anatomia do trecho ao clicar num resultado da busca", async () => {
    mockApi();
    renderPage();
    const user = userEvent.setup();

    await user.type(await screen.findByLabelText("Pergunta de teste"), "vpn");
    await user.click(screen.getByRole("button", { name: "Rastrear" }));
    await screen.findByText("rastreio de 26,1 ms");
    await user.click(screen.getByRole("button", { name: /^Busca dupla/ }));
    const results = await screen.findAllByRole("button", { name: /VPN > Conexão/ });
    await user.click(results[0]!);

    expect(await screen.findByText("Para conectar a VPN, abra o cliente.")).toBeTruthy();
    expect(screen.getByText(/Radicais guardados/i)).toBeTruthy();
  });
});
