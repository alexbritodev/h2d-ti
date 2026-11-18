import {
  AlertCircle,
  Bot,
  CheckCheck,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Circle,
  Clock,
  Loader2,
  Search,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

import type { AgentName, AgentProgressEvent, AgentStatus } from "./api";

interface AgentProgressPanelProps {
  events: AgentProgressEvent[];
  isStreaming?: boolean;
}

interface StageDefinition {
  key: AgentName;
  name: string;
  roleDescription: string;
  icon: typeof ShieldCheck;
}

const STAGES: StageDefinition[] = [
  {
    key: "guardiao",
    name: "Guardião de Entrada",
    roleDescription: "Filtro de segurança e conteúdo",
    icon: ShieldCheck,
  },
  {
    key: "rag",
    name: "Busca nos Manuais",
    roleDescription: "Recuperação RAG na base de conhecimento",
    icon: Search,
  },
  {
    key: "llm",
    name: "Geração da Resposta",
    roleDescription: "Síntese técnica com base nos trechos",
    icon: Bot,
  },
  {
    key: "validador",
    name: "Validador de Resposta",
    roleDescription: "Juiz anti-alucinação e fidelidade",
    icon: CheckCheck,
  },
];

function getStatusBadge(status: AgentStatus) {
  switch (status) {
    case "em_andamento":
      return <Badge tone="info" className="animate-pulse">Em andamento</Badge>;
    case "aprovado":
      return <Badge tone="accent">Aprovado</Badge>;
    case "reprovado":
      return <Badge tone="danger">Reprovado</Badge>;
    case "erro":
      return <Badge tone="warn">Atenção</Badge>;
    case "aguardando":
    default:
      return <Badge tone="neutral">Aguardando</Badge>;
  }
}

function getStatusIcon(status: AgentStatus) {
  switch (status) {
    case "em_andamento":
      return <Loader2 className="size-4 animate-spin text-info" aria-label="Processando" />;
    case "aprovado":
      return <CheckCircle2 className="size-4 text-accent" aria-label="Aprovado" />;
    case "reprovado":
      return <XCircle className="size-4 text-danger" aria-label="Reprovado" />;
    case "erro":
      return <AlertCircle className="size-4 text-warn" aria-label="Erro" />;
    case "aguardando":
    default:
      return <Circle className="size-4 text-muted/50" aria-label="Aguardando" />;
  }
}

export function AgentProgressPanel({ events, isStreaming }: AgentProgressPanelProps) {
  const [isOpen, setIsOpen] = useState(true);
  const [expandedDetails, setExpandedDetails] = useState<Record<string, boolean>>({});

  // Se não houver eventos ainda mas está processando, mostra etapas iniciais
  if (!events.length && !isStreaming) {
    return null;
  }

  // Mapeia o evento mais recente de cada agente
  const latestByAgent = new Map<AgentName, AgentProgressEvent>();
  for (const ev of events) {
    latestByAgent.set(ev.agente, ev);
  }

  const toggleDetails = (key: string) => {
    setExpandedDetails((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const hasAnyRejection = events.some((e) => e.status === "reprovado");
  const isAllApproved =
    events.length > 0 &&
    STAGES.every((s) => latestByAgent.get(s.key)?.status === "aprovado");

  return (
    <div
      className={cn(
        "my-2 rounded-xl border transition-all duration-200",
        hasAnyRejection
          ? "border-danger/30 bg-danger-soft/10"
          : isStreaming
            ? "border-info/30 bg-info/5 shadow-xs"
            : "border-border/80 bg-surface-2/40",
      )}
      data-testid="agent-progress-panel"
    >
      {/* Cabeçalho do Painel com Resumo e Toggle de Recolher/Expandir */}
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className="flex w-full cursor-pointer items-center justify-between px-3.5 py-2.5 text-left select-none hover:opacity-90"
        aria-expanded={isOpen}
      >
        <div className="flex items-center gap-2">
          {isStreaming ? (
            <span className="flex size-2 rounded-full bg-info animate-ping" />
          ) : hasAnyRejection ? (
            <XCircle className="size-4 text-danger" />
          ) : isAllApproved ? (
            <CheckCircle2 className="size-4 text-accent" />
          ) : (
            <Clock className="size-4 text-muted" />
          )}
          <span className="text-xs font-semibold tracking-tight text-text">
            Pipeline de Agentes
          </span>
          <span className="text-[11px] text-muted">
            {isStreaming
              ? "· Processando em tempo real..."
              : hasAnyRejection
                ? "· Interrompido por política ou validação"
                : "· Verificação concluída"}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {!isOpen && (
            <div className="flex items-center gap-1.5">
              {STAGES.map((stage) => {
                const ev = latestByAgent.get(stage.key);
                const status: AgentStatus = ev?.status ?? "aguardando";
                return (
                  <span
                    key={stage.key}
                    title={`${stage.name}: ${status}`}
                    className="inline-flex items-center"
                  >
                    {getStatusIcon(status)}
                  </span>
                );
              })}
            </div>
          )}
          {isOpen ? (
            <ChevronUp className="size-4 text-muted" />
          ) : (
            <ChevronDown className="size-4 text-muted" />
          )}
        </div>
      </button>

      {/* Conteúdo Expansível: Timeline / Stepper */}
      {isOpen && (
        <div className="border-t border-border/40 px-3.5 py-3">
          <ol className="relative space-y-4 border-l border-border/60 ml-2.5 pl-4">
            {STAGES.map((stage) => {
              const ev = latestByAgent.get(stage.key);
              const status: AgentStatus = ev?.status ?? (isStreaming ? "aguardando" : "aguardando");
              const message = ev?.mensagem ?? "Aguardando início da etapa...";
              const details = ev?.detalhes;
              const hasDetails = details && Object.keys(details).length > 0;
              const isDetailsOpen = Boolean(expandedDetails[stage.key]);

              return (
                <li key={stage.key} className="group relative">
                  {/* Ponto / Ícone na linha do tempo */}
                  <span
                    className={cn(
                      "absolute -left-[25px] flex size-5 items-center justify-center rounded-full bg-surface shadow-xs ring-2",
                      status === "em_andamento"
                        ? "ring-info/50"
                        : status === "aprovado"
                          ? "ring-accent/50"
                          : status === "reprovado"
                            ? "ring-danger/50"
                            : status === "erro"
                              ? "ring-warn/50"
                              : "ring-border",
                    )}
                  >
                    {getStatusIcon(status)}
                  </span>

                  {/* Informações da Etapa */}
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium text-text">{stage.name}</span>
                      <span className="text-[10px] text-muted hidden sm:inline">
                        ({stage.roleDescription})
                      </span>
                    </div>
                    <div>{getStatusBadge(status)}</div>
                  </div>

                  <p className="mt-1 text-xs text-muted-fg leading-relaxed">{message}</p>

                  {/* Alerta destacado em caso de reprovação ou erro */}
                  {status === "reprovado" && details && Boolean(details.motivo) && (
                    <div className="mt-2 rounded-lg bg-danger-soft/30 p-2 text-xs text-danger border border-danger/20">
                      <strong>Motivo:</strong> {String(details.motivo)}
                    </div>
                  )}

                  {/* Toggle para detalhes técnicos */}
                  {hasDetails && (
                    <div className="mt-2">
                      <button
                        type="button"
                        onClick={() => toggleDetails(stage.key)}
                        className="inline-flex items-center gap-1 text-[11px] font-medium text-accent hover:underline cursor-pointer"
                      >
                        {isDetailsOpen ? "Ocultar detalhes" : "Ver detalhes técnicos"}
                        {isDetailsOpen ? (
                          <ChevronUp className="size-3" />
                        ) : (
                          <ChevronDown className="size-3" />
                        )}
                      </button>

                      {isDetailsOpen && (
                        <div className="mt-1.5 rounded-lg bg-surface/80 p-2.5 text-[11px] font-mono border border-border/60 space-y-1">
                          {details.categoria != null && (
                            <p>
                              <span className="text-muted">Categoria:</span>{" "}
                              <span className="font-semibold">{String(details.categoria)}</span>
                            </p>
                          )}
                          {details.camada != null && (
                            <p>
                              <span className="text-muted">Camada de detecção:</span>{" "}
                              {String(details.camada)}
                            </p>
                          )}
                          {details.confianca !== undefined && (
                            <p>
                              <span className="text-muted">Índice de Confiança:</span>{" "}
                              <span className="font-semibold text-accent">
                                {Math.round(Number(details.confianca) * 100)}%
                              </span>
                            </p>
                          )}
                          {Array.isArray(details.afirmacoes_sem_respaldo) &&
                            details.afirmacoes_sem_respaldo.length > 0 && (
                              <div className="mt-1 text-danger">
                                <span className="text-muted">Afirmações sem respaldo:</span>
                                <ul className="list-disc pl-4 mt-0.5 space-y-0.5">
                                  {details.afirmacoes_sem_respaldo.map((item, idx) => (
                                    <li key={idx}>{String(item)}</li>
                                  ))}
                                </ul>
                              </div>
                            )}
                          {Array.isArray(details.documentos) && details.documentos.length > 0 && (
                            <div>
                              <span className="text-muted">Manuais consultados:</span>
                              <div className="flex flex-wrap gap-1 mt-1">
                                {details.documentos.map((doc, idx) => (
                                  <Badge key={idx} tone="info">
                                    {String(doc)}
                                  </Badge>
                                ))}
                              </div>
                            </div>
                          )}
                          {details.fontes_citadas != null && (
                            <p>
                              <span className="text-muted">Fontes citadas:</span>{" "}
                              {String(details.fontes_citadas)}
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </li>
              );
            })}
          </ol>
        </div>
      )}
    </div>
  );
}
