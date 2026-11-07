import type { AgentEvent, RoomKey } from "./engine";

/** Cenários roteirizados do modo demonstração. Rodam só no navegador: nada vai ao banco. */
export interface DemoScenario {
  id: string;
  title: string;
  description: string;
}

export const DEMO_SCENARIOS: readonly DemoScenario[] = [
  {
    id: "rag",
    title: "Dúvida resolvida pela base",
    description: "O chatbot acha a resposta nos manuais e responde com a fonte.",
  },
  {
    id: "status",
    title: "Consulta de status ao banco",
    description: "O usuário pergunta do chamado e o sistema lê o banco, só leitura.",
  },
  {
    id: "escalonamento",
    title: "Escalonamento para técnico",
    description: "Sem resposta na base: classifica, abre o chamado e atribui a um técnico.",
  },
];

type Step = [room: RoomKey, action: string, summary: string, agent?: string];

const SCRIPTS: Record<string, { steps: Step[]; ticket?: string }> = {
  rag: {
    steps: [
      ["recepcao", "mensagem_recebida", "Mensagem recebida do usuário"],
      ["rag", "rag_busca", "Busca na base: 3 trecho(s) encontrado(s)"],
      ["recepcao", "resposta_enviada", "Resposta enviada ao usuário"],
    ],
  },
  status: {
    steps: [
      ["recepcao", "mensagem_recebida", "Mensagem recebida do usuário"],
      ["banco", "sql_leitura", "Consulta de leitura em tickets: 1 chamado"],
      ["recepcao", "resposta_enviada", "Resposta enviada ao usuário"],
    ],
    ticket: "H2D-0042",
  },
  escalonamento: {
    steps: [
      ["recepcao", "mensagem_recebida", "Mensagem recebida do usuário"],
      ["rag", "rag_busca", "Busca na base: 0 trecho(s) encontrado(s)"],
      ["triagem", "classificado", "Categoria VPN · prioridade P2"],
      ["banco", "sql_leitura", "Consulta de leitura em technicians: 4 técnico(s)"],
      ["tecnicos", "chamado_criado", "Chamado H2D-0042 criado"],
      ["tecnicos", "chamado_atribuido", "Chamado H2D-0042 atribuído a Técnico Demo"],
      ["auditoria", "evento_registrado", "Chamado e classificação gravados na linha do tempo"],
      ["recepcao", "resposta_enviada", "Resposta enviada ao usuário"],
    ],
    ticket: "H2D-0042",
  },
};

const AGENTS: Record<RoomKey, string> = {
  recepcao: "Chatbot",
  triagem: "Classificador",
  rag: "Busca RAG",
  banco: "Consulta ao banco",
  tecnicos: "Roteador",
  auditoria: "Auditor",
};

/** Eventos do cenário, com horários espaçados a partir de `start` (para o log ter relógio). */
export function demoEvents(scenarioId: string, start: Date = new Date()): AgentEvent[] {
  const script = SCRIPTS[scenarioId];
  if (!script) return [];
  const conversation = `demo-${scenarioId}`;
  return script.steps.map(([room, action, summary, agent], index) => ({
    id: `${conversation}-${String(index).padStart(2, "0")}`,
    conversation_id: conversation,
    ticket_id: script.ticket ? `${conversation}-ticket` : null,
    room,
    action,
    summary,
    agent_name: agent ?? AGENTS[room],
    metadata: script.ticket ? { codigo: script.ticket } : {},
    created_at: new Date(start.getTime() + index * 2000).toISOString(),
  }));
}
