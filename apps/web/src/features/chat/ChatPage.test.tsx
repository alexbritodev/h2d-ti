import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ChatPage, resetChatSessionCache } from "./ChatPage";

const USER = {
  id: "0190a000-0000-7000-8000-000000000001",
  name: "Ana Admin",
  email: "admin@h2d.local",
  role: "admin" as const,
  department: "TI",
};

function sseStream(events: Array<{ event: string; data: unknown }>) {
  const payload = events
    .map((e) => `event: ${e.event}\ndata: ${JSON.stringify(e.data)}\n\n`)
    .join("");
  return new ReadableStream({
    start(controller) {
      controller.enqueue(new TextEncoder().encode(payload));
      controller.close();
    },
  });
}

function renderChat() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ChatPage />
    </QueryClientProvider>,
  );
}

describe("ChatPage", () => {
  beforeEach(() => {
    resetChatSessionCache();
    window.sessionStorage.clear();
  });

  afterEach(() => {
    cleanup();
    resetChatSessionCache();
    window.sessionStorage.clear();
    vi.unstubAllGlobals();
  });

  it("mantém o histórico da conversa e o painel de agentes ao desmontar e voltar para a tela", async () => {
    const convId = "0190a000-0000-7000-8000-000000000099";
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      const pathname = new URL(url, "http://localhost").pathname;

      if (pathname === "/api/auth/me") {
        return new Response(JSON.stringify(USER), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (pathname === "/api/chat/conversations") {
        const method = input instanceof Request ? input.method : "GET";
        if (method === "POST") {
          return new Response(
            JSON.stringify({
              id: convId,
              title: null,
              status: "open",
              created_at: "2026-11-18T11:00:00Z",
              updated_at: "2026-11-18T11:00:00Z",
            }),
            { status: 201, headers: { "Content-Type": "application/json" } },
          );
        }
        return new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (pathname === `/api/chat/conversations/${convId}/messages`) {
        return new Response(
          sseStream([
            {
              event: "agent_progress",
              data: {
                agente: "guardiao",
                status: "aprovado",
                mensagem: "Mensagem aprovada.",
                timestamp: "2026-11-18T11:00:00Z",
              },
            },
            { event: "token", data: { text: "Use df -h para ver o disco [1]." } },
            {
              event: "done",
              data: {
                message_id: "0190a000-0000-7000-8000-000000000100",
                action: "answered",
                conversation_status: "open",
                ticket: null,
              },
            },
          ]),
          { status: 200, headers: { "Content-Type": "text/event-stream" } },
        );
      }
      return new Response(JSON.stringify({ detail: "not found" }), { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    const firstMount = renderChat();
    const user = userEvent.setup();

    const input = await screen.findByLabelText("Sua mensagem");
    await user.type(input, "Como verifico espaço em disco no Linux?");
    await user.click(screen.getByRole("button", { name: "Enviar" }));

    expect(await screen.findByText(/Use df -h para ver o disco/)).toBeTruthy();
    expect(screen.getByText("Mensagem aprovada.")).toBeTruthy();

    // Simula troca de tela (desmonta ChatPage) e retorno para /chat (remonta ChatPage)
    firstMount.unmount();
    renderChat();

    await waitFor(() => {
      expect(screen.getByText("Como verifico espaço em disco no Linux?")).toBeTruthy();
      expect(screen.getByText(/Use df -h para ver o disco/)).toBeTruthy();
      expect(screen.getByText("Mensagem aprovada.")).toBeTruthy();
    });

    // Clicar em "Nova conversa" limpa o histórico e não restaura ao remontar
    await user.click(screen.getByRole("button", { name: /Nova conversa/ }));
    expect(screen.queryByText(/Use df -h para ver o disco/)).toBeNull();
  });
});
