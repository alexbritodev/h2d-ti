import { Bot, BookText, CheckCircle2, Route, UserRoundCheck } from "lucide-react";

import { PriorityBadge, SlaCell, StatusBadge } from "@/components/tickets";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Avatar, Drawer, Tabs, Timeline } from "@/components/ui/primitives";
import { demoToast } from "@/components/ui/toast";
import type { Ticket } from "@/lib/demo/data";

export function TicketDrawer({
  ticket,
  onClose,
  readOnly,
}: {
  ticket: Ticket | null;
  onClose: () => void;
  readOnly?: boolean;
}) {
  return (
    <Drawer
      open={ticket !== null}
      onOpenChange={(open) => !open && onClose()}
      title={ticket ? <span className="font-mono">{ticket.code}</span> : ""}
      description={ticket?.subject}
      footer={
        ticket && !readOnly ? (
          <>
            <Button
              className="border border-border"
              onClick={() => demoToast(`Reatribuição simulada de ${ticket.code}`)}
            >
              Reatribuir
            </Button>
            <Button variant="primary" onClick={() => demoToast(`${ticket.code} marcado como resolvido`)}>
              <CheckCircle2 aria-hidden className="size-4" />
              Resolver chamado
            </Button>
          </>
        ) : undefined
      }
    >
      {ticket && (
        <div className="space-y-5">
          <div className="flex flex-wrap items-center gap-2">
            <PriorityBadge priority={ticket.priority} />
            <StatusBadge status={ticket.status} />
            <Badge>{ticket.category}</Badge>
          </div>

          <dl className="grid grid-cols-2 gap-4 rounded-lg bg-surface-2 p-4">
            <div>
              <dt className="text-xs text-muted">Solicitante</dt>
              <dd className="font-medium">{ticket.requester}</dd>
              <dd className="text-xs text-muted">{ticket.department}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted">Responsável</dt>
              <dd className="flex items-center gap-2 font-medium">
                {ticket.assignee ? (
                  <>
                    <Avatar name={ticket.assignee} className="size-6 text-[10px]" />
                    {ticket.assignee}
                  </>
                ) : (
                  "Sem responsável"
                )}
              </dd>
            </div>
            <div className="col-span-2">
              <dt className="mb-1 text-xs text-muted">Prazo de SLA</dt>
              <dd>
                <SlaCell used={ticket.slaUsed} left={ticket.slaLeft} />
              </dd>
            </div>
          </dl>

          <Tabs
            label="Detalhes do chamado"
            tabs={[
              {
                value: "resumo",
                label: "Resumo da IA",
                content: (
                  <div className="space-y-4">
                    <div>
                      <h3 className="mb-1 flex items-center gap-2 font-semibold">
                        <Bot aria-hidden className="size-4 text-accent" />
                        Resumo
                        <Badge tone={ticket.confidence >= 0.7 ? "accent" : "warn"}>
                          Confiança {Math.round(ticket.confidence * 100)}%
                        </Badge>
                      </h3>
                      <p>{ticket.summary}</p>
                    </div>
                    <div>
                      <h3 className="mb-1 font-semibold">Já tentado</h3>
                      <ul className="list-disc space-y-1 pl-5 text-muted">
                        {ticket.tried.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </div>
                    <div>
                      <h3 className="mb-1 flex items-center gap-2 font-semibold">
                        <Route aria-hidden className="size-4 text-accent" />
                        Motivo da atribuição
                      </h3>
                      <p className="text-muted">{ticket.assignmentReason}</p>
                    </div>
                  </div>
                ),
              },
              {
                value: "fontes",
                label: "Fontes",
                count: ticket.sources.length,
                content:
                  ticket.sources.length > 0 ? (
                    <ul className="space-y-2">
                      {ticket.sources.map((source) => (
                        <li
                          key={source}
                          className="flex items-center gap-2 rounded-lg border border-border p-3"
                        >
                          <BookText aria-hidden className="size-4 shrink-0 text-muted" />
                          {source}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-muted">O assistente não consultou nenhum documento.</p>
                  ),
              },
              {
                value: "historico",
                label: "Histórico",
                content: (
                  <Timeline
                    items={[
                      {
                        id: "update",
                        title: "Última atualização",
                        time: ticket.updatedAt,
                        tone: "accent",
                      },
                      {
                        id: "assign",
                        title: ticket.assignee
                          ? `Atribuído a ${ticket.assignee}`
                          : "Enviado para a triagem manual",
                        detail: ticket.assignmentReason,
                        time: "Na abertura",
                        tone: ticket.assignee ? "info" : "warn",
                      },
                      {
                        id: "create",
                        title: "Chamado criado pelo assistente",
                        detail: `Classificado com ${Math.round(ticket.confidence * 100)}% de confiança`,
                        time: "Na abertura",
                      },
                    ]}
                  />
                ),
              },
              ...(readOnly
                ? []
                : [
                    {
                      value: "solucao",
                      label: "Solução",
                      content: (
                        <form
                          onSubmit={(event) => {
                            event.preventDefault();
                            demoToast("Solução registrada");
                          }}
                          className="space-y-3"
                        >
                          <label htmlFor="solution" className="block font-medium">
                            Solução aplicada
                          </label>
                          <textarea
                            id="solution"
                            rows={5}
                            placeholder="Descreva o que resolveu. O texto pode virar um artigo da base."
                            className="w-full rounded-lg border border-border bg-surface p-3 placeholder:text-muted"
                          />
                          <Button type="submit" className="border border-border">
                            <UserRoundCheck aria-hidden className="size-4" />
                            Registrar solução
                          </Button>
                        </form>
                      ),
                    },
                  ]),
            ]}
          />
        </div>
      )}
    </Drawer>
  );
}
