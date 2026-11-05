import { Bot, FileText, Headset, SendHorizontal, ThumbsDown, ThumbsUp } from "lucide-react";
import { type FormEvent, useState } from "react";

import { PageHeader } from "@/components/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Avatar, Card, CardHeader } from "@/components/ui/primitives";
import { Snippet } from "@/components/ui/snippet";
import { demoToast } from "@/components/ui/toast";
import { ARTICLES } from "@/lib/demo/data";
import { cn } from "@/lib/utils";

interface Message {
  id: number;
  from: "user" | "bot";
  text: string;
  snippet?: { language: string; code: string };
  citation?: string;
}

const VPN = ARTICLES.find((article) => article.id === "vpn-809")!;

const INITIAL_MESSAGES: Message[] = [
  { id: 1, from: "user", text: "Minha VPN não conecta e aparece erro 809." },
  {
    id: 2,
    from: "bot",
    text: "O erro 809 costuma acontecer quando a rede bloqueia o tráfego da VPN. Com a internet funcionando, rode este comando no PowerShell como administrador e reinicie o computador:",
    snippet: VPN.snippet,
    citation: "VPN no Windows: erro 809",
  },
];

const SOURCES = [
  {
    title: "VPN no Windows: erro 809",
    path: "Manual de VPN v3 › Windows › Erro 809",
    excerpt: "Quando o erro 809 aparece, confira se a rede bloqueia a porta usada pela VPN...",
    score: 94,
  },
  {
    title: "Requisitos de rede",
    path: "Manual de VPN v3 › Requisitos",
    excerpt: "A VPN exige as portas UDP 500 e 4500 liberadas na rede de origem...",
    score: 78,
  },
];

export function ChatPage() {
  const [messages, setMessages] = useState(INITIAL_MESSAGES);
  const [draft, setDraft] = useState("");
  const [feedback, setFeedback] = useState<Record<number, "up" | "down">>({});

  function send(event: FormEvent) {
    event.preventDefault();
    const text = draft.trim();
    if (!text) return;
    setMessages((current) => [
      ...current,
      { id: current.length + 1, from: "user", text },
      {
        id: current.length + 2,
        from: "bot",
        text: "Esta é uma resposta de demonstração. O assistente de verdade entra na fase F3, consultando os manuais e citando a fonte.",
      },
    ]);
    setDraft("");
  }

  return (
    <section>
      <PageHeader
        title="Assistente"
        description="Descreva o problema e receba a resposta com base nos manuais de TI."
        actions={
          <Button
            className="border border-border bg-surface"
            onClick={() => demoToast("Chamado aberto com o resumo da conversa")}
          >
            <Headset aria-hidden className="size-4" />
            Falar com a TI
          </Button>
        }
      />

      <div className="grid gap-4 xl:grid-cols-3">
        <Card className="flex min-h-[520px] flex-col xl:col-span-2">
          <ol aria-label="Conversa" className="flex-1 space-y-5 overflow-y-auto p-5">
            {messages.map((message) =>
              message.from === "user" ? (
                <li key={message.id} className="flex justify-end">
                  <p className="max-w-[80%] rounded-2xl rounded-br-sm bg-accent px-4 py-2.5 text-accent-fg">
                    {message.text}
                  </p>
                </li>
              ) : (
                <li key={message.id} className="flex gap-3">
                  <span
                    aria-hidden
                    className="flex size-8 shrink-0 items-center justify-center rounded-full bg-accent-soft text-accent"
                  >
                    <Bot className="size-[18px]" />
                  </span>
                  <div className="min-w-0 flex-1 space-y-3">
                    <p>{message.text}</p>
                    {message.snippet && <Snippet {...message.snippet} />}
                    {message.citation && (
                      <Badge tone="info">
                        <FileText aria-hidden className="size-3" />
                        Fonte: {message.citation}
                      </Badge>
                    )}
                    <div className="flex items-center gap-1 text-xs text-muted">
                      <span className="mr-1">Resolveu?</span>
                      {(
                        [
                          ["up", ThumbsUp, "Resposta útil"],
                          ["down", ThumbsDown, "Resposta não ajudou"],
                        ] as const
                      ).map(([value, Icon, label]) => (
                        <button
                          key={value}
                          type="button"
                          aria-label={label}
                          aria-pressed={feedback[message.id] === value}
                          onClick={() =>
                            setFeedback((current) => ({ ...current, [message.id]: value }))
                          }
                          className={cn(
                            "flex size-8 cursor-pointer items-center justify-center rounded-lg hover:bg-surface-2",
                            feedback[message.id] === value && "bg-accent-soft text-accent",
                          )}
                        >
                          <Icon aria-hidden className="size-4" />
                        </button>
                      ))}
                    </div>
                  </div>
                </li>
              ),
            )}
          </ol>
          <form onSubmit={send} className="flex gap-2 border-t border-border p-4">
            <Input
              aria-label="Sua mensagem"
              placeholder="Descreva o problema. Nunca informe sua senha."
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
            />
            <Button type="submit" variant="primary" aria-label="Enviar" className="w-12 shrink-0 px-0">
              <SendHorizontal aria-hidden className="size-[18px]" />
            </Button>
          </form>
          <p className="px-4 pb-3 text-xs text-muted">
            Respostas geradas por IA a partir dos manuais. Confira a fonte antes de seguir um
            procedimento.
          </p>
        </Card>

        <Card className="self-start">
          <CardHeader title="Fontes consultadas" description="Trechos usados na última resposta" />
          <ul className="divide-y divide-border">
            {SOURCES.map((source) => (
              <li key={source.title} className="space-y-1.5 p-4">
                <div className="flex items-start justify-between gap-2">
                  <p className="font-medium">{source.title}</p>
                  <Badge tone="accent">{source.score}%</Badge>
                </div>
                <p className="font-mono text-[11px] text-muted">{source.path}</p>
                <p className="text-muted">{source.excerpt}</p>
              </li>
            ))}
          </ul>
          <div className="flex items-center gap-2 border-t border-border p-4 text-xs text-muted">
            <Avatar name="Base Conhecimento" className="size-6 text-[10px]" />
            Base atualizada há 2 dias
          </div>
        </Card>
      </div>
    </section>
  );
}
