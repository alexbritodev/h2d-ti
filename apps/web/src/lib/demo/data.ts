/**
 * Dados fictícios das telas que ainda não têm backend. Cada módulo troca este arquivo
 * pela API na fase indicada em docs/PLANO-IMPLEMENTACAO.md. Nada aqui é real.
 */
export type Priority = "P1" | "P2" | "P3" | "P4";
export type TicketStatus = "triagem" | "aberto" | "andamento" | "aguardando" | "resolvido";

export interface Ticket {
  code: string;
  subject: string;
  category: string;
  priority: Priority;
  status: TicketStatus;
  requester: string;
  department: string;
  assignee: string | null;
  slaUsed: number;
  slaLeft: string;
  updatedAt: string;
  confidence: number;
  summary: string;
  tried: string[];
  sources: string[];
  assignmentReason: string;
}

export const TICKETS: Ticket[] = [
  {
    code: "H2D-0142",
    subject: "VPN cai com erro 809 ao conectar de casa",
    category: "Rede e VPN",
    priority: "P2",
    status: "andamento",
    requester: "Fátima Financeiro",
    department: "Financeiro",
    assignee: "Rita Redes",
    slaUsed: 62,
    slaLeft: "3 h 02 restantes",
    updatedAt: "há 12 min",
    confidence: 0.91,
    summary:
      "Usuária não conecta à VPN desde a manhã, com erro 809 no Windows 11. Afeta o fechamento do mês.",
    tried: ["Bot sugeriu reiniciar o cliente de VPN", "Usuária testou em outra rede, sem sucesso"],
    sources: ["VPN > Windows > Erro 809", "VPN > Requisitos de rede"],
    assignmentReason: "Tem a habilidade redes-vpn e a menor carga ponderada entre os elegíveis.",
  },
  {
    code: "H2D-0141",
    subject: "Sistema de faturamento fora do ar para todo o setor",
    category: "Sistemas internos",
    priority: "P1",
    status: "andamento",
    requester: "Marcos Marketing",
    department: "Marketing",
    assignee: "Túlio Técnico",
    slaUsed: 88,
    slaLeft: "29 min restantes",
    updatedAt: "há 4 min",
    confidence: 0.96,
    summary: "Sistema retorna erro 502 para 14 pessoas desde as 9h. Tema crítico: o bot não tentou resolver.",
    tried: ["Nenhuma tentativa: escalonado direto por ser tema crítico"],
    sources: [],
    assignmentReason: "Tema crítico. Tem a habilidade sistemas-internos; líder avisado por ser P1.",
  },
  {
    code: "H2D-0140",
    subject: "Recebi e-mail suspeito pedindo senha do banco",
    category: "Segurança",
    priority: "P1",
    status: "aberto",
    requester: "Diana Diretoria",
    department: "Diretoria",
    assignee: "Rita Redes",
    slaUsed: 104,
    slaLeft: "Estourado há 9 min",
    updatedAt: "há 2 min",
    confidence: 0.94,
    summary: "Possível phishing direcionado à diretoria. Usuária não clicou no link. Solicitante VIP.",
    tried: ["Bot orientou a não clicar e a não responder"],
    sources: ["Segurança > Como identificar phishing"],
    assignmentReason: "Tem a habilidade seguranca. Líder avisado por ser P1.",
  },
  {
    code: "H2D-0139",
    subject: "Impressora do 3º andar imprime tudo em branco",
    category: "Impressão",
    priority: "P3",
    status: "aberto",
    requester: "Marcos Marketing",
    department: "Marketing",
    assignee: "Sérgio Suporte",
    slaUsed: 34,
    slaLeft: "15 h 50 restantes",
    updatedAt: "há 38 min",
    confidence: 0.88,
    summary: "Páginas saem em branco desde a troca de toner. Teste de impressão com o mesmo resultado.",
    tried: ["Bot sugeriu limpeza de cabeça e reinstalar o toner"],
    sources: ["Impressoras > Páginas em branco"],
    assignmentReason: "Tem a habilidade impressoras e capacidade disponível.",
  },
  {
    code: "H2D-0138",
    subject: "Preciso de acesso ao sistema de RH",
    category: "Acessos e senhas",
    priority: "P4",
    status: "aguardando",
    requester: "Fátima Financeiro",
    department: "Financeiro",
    assignee: "Túlio Técnico",
    slaUsed: 21,
    slaLeft: "2 d 8 h restantes",
    updatedAt: "há 1 h",
    confidence: 0.83,
    summary: "Pedido de acesso de leitura ao sistema de RH. Falta a aprovação do gestor.",
    tried: ["Bot explicou o processo de solicitação de acesso"],
    sources: ["Acessos > Solicitar acesso a sistemas"],
    assignmentReason: "Tem a habilidade identidade-acesso.",
  },
  {
    code: "H2D-0137",
    subject: "Notebook muito lento depois da atualização",
    category: "Equipamentos",
    priority: "P3",
    status: "andamento",
    requester: "Marcos Marketing",
    department: "Marketing",
    assignee: "Sérgio Suporte",
    slaUsed: 78,
    slaLeft: "5 h 16 restantes",
    updatedAt: "há 2 h",
    confidence: 0.72,
    summary: "Lentidão após atualização do Windows. Disco com 96% de uso.",
    tried: ["Bot sugeriu liberar espaço e reiniciar"],
    sources: ["Equipamentos > Notebook lento"],
    assignmentReason: "Tem a habilidade hardware e a menor carga.",
  },
  {
    code: "H2D-0136",
    subject: "Problema estranho, não sei explicar direito",
    category: "A classificar",
    priority: "P3",
    status: "triagem",
    requester: "Diana Diretoria",
    department: "Diretoria",
    assignee: null,
    slaUsed: 12,
    slaLeft: "21 h 07 restantes",
    updatedAt: "há 3 h",
    confidence: 0.41,
    summary: "Descrição vaga, sem sistema nem mensagem de erro. O classificador não atingiu a confiança mínima.",
    tried: ["Bot fez 3 perguntas de esclarecimento, sem resposta conclusiva"],
    sources: [],
    assignmentReason: "Confiança abaixo do limiar: foi para a triagem manual.",
  },
  {
    code: "H2D-0135",
    subject: "Calendário não sincroniza no celular",
    category: "E-mail e colaboração",
    priority: "P4",
    status: "resolvido",
    requester: "Fátima Financeiro",
    department: "Financeiro",
    assignee: "Túlio Técnico",
    slaUsed: 40,
    slaLeft: "Resolvido no prazo",
    updatedAt: "ontem",
    confidence: 0.9,
    summary: "Conta precisava ser adicionada de novo depois da troca de senha.",
    tried: ["Bot sugeriu verificar a conexão"],
    sources: ["E-mail > Configurar no celular"],
    assignmentReason: "Tem a habilidade email-colaboracao.",
  },
  {
    code: "H2D-0134",
    subject: "Wi-Fi da sala de reunião desconecta toda hora",
    category: "Rede e VPN",
    priority: "P3",
    status: "aberto",
    requester: "Diana Diretoria",
    department: "Diretoria",
    assignee: "Rita Redes",
    slaUsed: 51,
    slaLeft: "11 h 45 restantes",
    updatedAt: "há 4 h",
    confidence: 0.86,
    summary: "Queda recorrente no Wi-Fi da sala 2. Outros dispositivos também são afetados.",
    tried: ["Bot sugeriu esquecer a rede e reconectar"],
    sources: ["Rede > Wi-Fi instável"],
    assignmentReason: "Tem a habilidade redes-vpn.",
  },
  {
    code: "H2D-0133",
    subject: "Conta bloqueada depois de errar a senha",
    category: "Acessos e senhas",
    priority: "P2",
    status: "resolvido",
    requester: "Marcos Marketing",
    department: "Marketing",
    assignee: "Túlio Técnico",
    slaUsed: 25,
    slaLeft: "Resolvido no prazo",
    updatedAt: "ontem",
    confidence: 0.95,
    summary: "Conta desbloqueada e senha redefinida pelo portal.",
    tried: ["Bot enviou o link de redefinição; o portal exigiu desbloqueio manual"],
    sources: ["Acessos > Redefinir senha"],
    assignmentReason: "Tem a habilidade identidade-acesso.",
  },
];

export const NOTIFICATIONS = [
  { id: "1", title: "SLA estourado", detail: "H2D-0140 passou do prazo de resposta", time: "há 9 min", urgent: true },
  { id: "2", title: "SLA em risco", detail: "H2D-0141 consumiu 88% do prazo", time: "há 12 min", urgent: true },
  { id: "3", title: "Triagem manual", detail: "H2D-0136 precisa de classificação", time: "há 3 h", urgent: false },
  { id: "4", title: "Documento publicado", detail: "Manual de VPN v3 entrou na base", time: "ontem", urgent: false },
];

export const VOLUME_BY_DAY = [
  18, 22, 19, 26, 31, 12, 9, 24, 28, 25, 33, 29, 11, 8,
].map((value, index) => ({ label: `${String(21 + index > 31 ? 21 + index - 31 : 21 + index).padStart(2, "0")}/${21 + index > 31 ? "11" : "10"}`, value }));

export const TICKETS_BY_CATEGORY = [
  { label: "Acessos e senhas", value: 46 },
  { label: "Rede e VPN", value: 38 },
  { label: "E-mail e colaboração", value: 27 },
  { label: "Impressão", value: 19 },
  { label: "Sistemas internos", value: 16 },
  { label: "Equipamentos", value: 12 },
];

export const KPIS = [
  { label: "Taxa de deflexão", value: "37%", delta: "+4 p.p.", positive: true, trend: [28, 30, 29, 33, 32, 35, 37], hint: "Resolvidas sem chamado" },
  { label: "SLA cumprido", value: "92%", delta: "-1 p.p.", positive: false, trend: [95, 94, 93, 94, 92, 93, 92], hint: "Chamados no prazo" },
  { label: "Tempo médio de resolução", value: "4 h 18", delta: "-22 min", positive: true, trend: [320, 305, 298, 290, 281, 270, 258], hint: "Todas as prioridades" },
  { label: "Custo por conversa", value: "R$ 0,14", delta: "+R$ 0,01", positive: false, trend: [11, 12, 12, 13, 13, 13, 14], hint: "Uso do modelo de IA" },
];

export const TECHNICIANS = [
  { name: "Túlio Técnico", email: "tecnico1@h2d.local", skills: ["identidade-acesso", "email-colaboracao", "sistemas-internos"], open: 7, capacity: 10, available: true, resolved: 41 },
  { name: "Rita Redes", email: "tecnico2@h2d.local", skills: ["redes-vpn", "seguranca"], open: 9, capacity: 10, available: true, resolved: 36 },
  { name: "Sérgio Suporte", email: "tecnico3@h2d.local", skills: ["impressoras", "hardware", "email-colaboracao"], open: 4, capacity: 10, available: false, resolved: 29 },
];

export const USERS = [
  { name: "Ana Admin", email: "admin@h2d.local", role: "Administrador", department: "TI", active: true, vip: false },
  { name: "Túlio Técnico", email: "tecnico1@h2d.local", role: "Técnico de TI", department: "TI", active: true, vip: false },
  { name: "Rita Redes", email: "tecnico2@h2d.local", role: "Técnico de TI", department: "TI", active: true, vip: false },
  { name: "Sérgio Suporte", email: "tecnico3@h2d.local", role: "Técnico de TI", department: "TI", active: true, vip: false },
  { name: "Fátima Financeiro", email: "usuario1@h2d.local", role: "Usuário", department: "Financeiro", active: true, vip: false },
  { name: "Marcos Marketing", email: "usuario2@h2d.local", role: "Usuário", department: "Marketing", active: true, vip: false },
  { name: "Diana Diretoria", email: "usuario3@h2d.local", role: "Usuário", department: "Diretoria", active: true, vip: true },
  { name: "Paulo Antigo", email: "paulo@h2d.local", role: "Usuário", department: "Compras", active: false, vip: false },
];

export const CATEGORIES = [
  { name: "Rede e VPN", children: 3, skill: "redes-vpn", sla: "Padrão", active: true },
  { name: "Acessos e senhas", children: 2, skill: "identidade-acesso", sla: "Padrão", active: true },
  { name: "E-mail e colaboração", children: 3, skill: "email-colaboracao", sla: "Padrão", active: true },
  { name: "Impressão", children: 2, skill: "impressoras", sla: "Padrão", active: true },
  { name: "Equipamentos", children: 2, skill: "hardware", sla: "Padrão", active: true },
  { name: "Sistemas internos", children: 2, skill: "sistemas-internos", sla: "Padrão", active: true },
  { name: "Segurança", children: 2, skill: "seguranca", sla: "Padrão", active: true },
];

export const SLA_TARGETS: { priority: Priority; firstResponse: string; resolution: string; compliance: number }[] = [
  { priority: "P1", firstResponse: "30 min", resolution: "4 h", compliance: 86 },
  { priority: "P2", firstResponse: "1 h", resolution: "8 h", compliance: 90 },
  { priority: "P3", firstResponse: "4 h", resolution: "24 h", compliance: 94 },
  { priority: "P4", firstResponse: "8 h", resolution: "3 d", compliance: 97 },
];

export interface Article {
  id: string;
  title: string;
  category: string;
  excerpt: string;
  visibility: "public" | "it";
  updatedAt: string;
  helpful: number;
  steps: string[];
  snippet?: { language: string; code: string };
}

export const ARTICLES: Article[] = [
  {
    id: "vpn-809",
    title: "VPN no Windows: erro 809",
    category: "Rede e VPN",
    excerpt: "O que fazer quando a VPN não conecta e mostra o erro 809.",
    visibility: "public",
    updatedAt: "há 2 dias",
    helpful: 94,
    steps: [
      "Confira se a internet funciona sem a VPN.",
      "Abra o PowerShell como administrador e rode o comando abaixo.",
      "Reinicie o computador e conecte de novo.",
    ],
    snippet: {
      language: "powershell",
      code: 'Set-ItemProperty -Path "HKLM:\\SYSTEM\\CurrentControlSet\\Services\\PolicyAgent" `\n  -Name "AssumeUDPEncapsulationContextOnSendRule" -Value 2 -Type DWord',
    },
  },
  {
    id: "senha",
    title: "Como redefinir sua senha",
    category: "Acessos e senhas",
    excerpt: "Passo a passo para trocar a senha pelo portal, sem abrir chamado.",
    visibility: "public",
    updatedAt: "há 1 semana",
    helpful: 98,
    steps: [
      "Acesse o portal de senhas da empresa.",
      "Informe seu e-mail e confirme o código recebido.",
      "Crie uma senha nova. Nunca envie sua senha pelo chat.",
    ],
  },
  {
    id: "dns",
    title: "Sites internos não abrem",
    category: "Rede e VPN",
    excerpt: "Como limpar o cache de DNS quando só os sistemas internos falham.",
    visibility: "public",
    updatedAt: "há 3 dias",
    helpful: 87,
    steps: ["Conecte-se à VPN.", "Rode o comando abaixo no Prompt de Comando.", "Tente abrir o site de novo."],
    snippet: { language: "cmd", code: "ipconfig /flushdns" },
  },
  {
    id: "impressora",
    title: "Impressora imprime páginas em branco",
    category: "Impressão",
    excerpt: "Verificações rápidas antes de chamar o suporte.",
    visibility: "public",
    updatedAt: "há 2 semanas",
    helpful: 81,
    steps: ["Retire o lacre do toner novo.", "Imprima a página de teste.", "Se continuar, abra um chamado."],
  },
  {
    id: "phishing",
    title: "Como identificar phishing",
    category: "Segurança",
    excerpt: "Sinais de e-mail falso e o que fazer ao receber um.",
    visibility: "public",
    updatedAt: "há 1 mês",
    helpful: 92,
    steps: ["Confira o remetente real.", "Não clique em links nem abra anexos.", "Avise a TI pelo assistente."],
  },
  {
    id: "firewall",
    title: "Liberar regra no firewall de borda",
    category: "Rede e VPN",
    excerpt: "Procedimento interno para abertura de porta, com aprovação.",
    visibility: "it",
    updatedAt: "há 5 dias",
    helpful: 76,
    steps: ["Confirme a aprovação no chamado.", "Teste a porta a partir do servidor de origem.", "Registre a regra."],
    snippet: {
      language: "powershell",
      code: "Test-NetConnection -ComputerName app.interno.exemplo -Port 443",
    },
  },
];

export const DOCUMENTS = [
  { id: "d1", title: "Manual de VPN", file: "manual-vpn.pdf", category: "Rede e VPN", visibility: "Público", version: "v3", status: "published", owner: "Rita Redes", expires: "12/2026" },
  { id: "d2", title: "Política de senhas", file: "politica-senhas.docx", category: "Acessos e senhas", visibility: "Público", version: "v2", status: "published", owner: "Túlio Técnico", expires: "03/2027" },
  { id: "d3", title: "Guia de impressoras", file: "guia-impressoras.pdf", category: "Impressão", visibility: "Público", version: "v1", status: "embedding", owner: "Sérgio Suporte", expires: "06/2027" },
  { id: "d4", title: "Runbook de firewall", file: "runbook-firewall.md", category: "Rede e VPN", visibility: "Só TI", version: "v5", status: "published", owner: "Rita Redes", expires: "11/2026" },
  { id: "d5", title: "Manual do e-mail", file: "manual-email.pdf", category: "E-mail e colaboração", visibility: "Público", version: "v1", status: "parsing", owner: "Túlio Técnico", expires: "08/2027" },
  { id: "d6", title: "Inventário antigo", file: "inventario.pdf", category: "Equipamentos", visibility: "Só TI", version: "v1", status: "failed", owner: "Sérgio Suporte", expires: "–" },
];

export const AUDIT_LOG = [
  { id: "a1", actor: "Ana Admin", action: "Alterou", entity: "Limiar de confiança", time: "04/11/2026 18:42", before: { limiar: 0.6 }, after: { limiar: 0.7 } },
  { id: "a2", actor: "Ana Admin", action: "Publicou", entity: "Documento: Manual de VPN v3", time: "04/11/2026 16:10", before: { versao: "v2" }, after: { versao: "v3" } },
  { id: "a3", actor: "Túlio Técnico", action: "Reatribuiu", entity: "Chamado H2D-0133", time: "04/11/2026 11:25", before: { responsavel: "Sérgio Suporte" }, after: { responsavel: "Túlio Técnico" } },
  { id: "a4", actor: "Ana Admin", action: "Desativou", entity: "Usuário: Paulo Antigo", time: "03/11/2026 17:03", before: { ativo: true }, after: { ativo: false } },
  { id: "a5", actor: "Ana Admin", action: "Alterou", entity: "SLA Padrão: P1", time: "03/11/2026 09:30", before: { primeira_resposta: "1 h" }, after: { primeira_resposta: "30 min" } },
  { id: "a6", actor: "Rita Redes", action: "Corrigiu categoria", entity: "Chamado H2D-0128", time: "02/11/2026 15:12", before: { categoria: "Equipamentos" }, after: { categoria: "Rede e VPN" } },
];

export const PROMPT_VERSIONS = [
  { version: "atendimento-v4", purpose: "Assistente", status: "Ativa", accuracy: "89%", date: "04/11/2026" },
  { version: "atendimento-v3", purpose: "Assistente", status: "Arquivada", accuracy: "84%", date: "28/10/2026" },
  { version: "triagem-v2", purpose: "Classificador", status: "Ativa", accuracy: "91%", date: "01/11/2026" },
];

export const ACTIVITY = [
  { id: "1", title: "Chamado H2D-0142 atribuído a Rita Redes", detail: "Menor carga entre os técnicos de redes", time: "há 12 min", tone: "accent" as const },
  { id: "2", title: "Assistente resolveu uma dúvida de senha", detail: "Fonte: Como redefinir sua senha", time: "há 18 min", tone: "info" as const },
  { id: "3", title: "SLA em risco em H2D-0141", detail: "O líder foi avisado", time: "há 25 min", tone: "warn" as const },
  { id: "4", title: "Manual de VPN v3 publicado", detail: "Versão anterior arquivada", time: "há 2 h", tone: "neutral" as const },
];
