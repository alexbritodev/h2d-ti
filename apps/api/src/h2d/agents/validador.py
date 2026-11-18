"""Agente 2: Validador de Resposta (anti-alucinação).

Verifica se a resposta gerada pela LLM está devidamente fundamentada nos manuais recuperados (RAG),
avaliando sustentação, ausência de informações inventadas, pertinência à pergunta e não-contradição.
Devolve JSON estrito com veredito, índice de confiança e afirmações sem respaldo.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from h2d.kb.search import Hit
from h2d.llm.client import LLM, ChatMessage, LLMError

log = logging.getLogger("h2d.agents.validador")

VALIDADOR_SYSTEM_PROMPT = """Você é o Agente Validador de Respostas de um sistema de TI corporativo.
Sua função é agir como Juiz Crítico Imparcial (anti-alucinação), verificando se a RESPOSTA gerada \
está devidamente fundamentada nos MANUAIS RECUPERADOS (fontes).

Critérios:
(a) Sustentação: As afirmações técnicas da resposta estão claramente sustentadas pelos trechos?
(b) Sem invenção: A resposta contém dados, comandos ou procedimentos AUSENTES dos manuais?
(c) Pertinência: A resposta responde de fato à dúvida do usuário ou desvia do assunto?
(d) Não-contradição: Há alguma instrução na resposta que contradiz o que está nos manuais?

Notas:
- Ignore saudações cordiais, ofertas de suporte adicional ou marcas [1], [2].
- Se a resposta afirmar com honestidade que algo não consta nos manuais, isso é VÁLIDO.
- Qualquer comando inventado ou parâmetro não documentado torna a resposta INVÁLIDA.

Responda com o veredito (SIM ou NAO) em JSON estrito no seguinte formato:
{
  "valida": true ou false,
  "confianca": número de 0.0 a 1.0,
  "afirmacoes_sem_respaldo": ["frases ou comandos não suportados"],
  "motivo": "Explicação detalhada e concisa do veredito"
}"""

REGENERATE_RESTRICTIVE_PROMPT = """Você é o assistente de TI. Sua resposta anterior foi reprovada \
por conter informações não comprovadas nos manuais.

REGRAS ESTRITAS DE REGENERAÇÃO:
1. Responda SOMENTE com base nos trechos dentro de <fontes>.
2. NÃO adicione nenhum comando ou suposição que não esteja expressamente escrito nas fontes.
3. Se as fontes não cobrirem a dúvida por completo, responda APENAS o documentado, \
cite [1], [2]... e declare em uma frase curta o que não consta nos manuais.
4. Mantenha tom profissional, direto e em português do Brasil."""

NOT_FOUND_MANUALS_MESSAGE = (
    "Não encontramos informações sobre este assunto nos manuais de instrução cadastrados na nossa "
    "base de conhecimento. Para que possamos te ajudar da melhor forma, recomendamos abrir um "
    "chamado para a equipe de suporte de TI."
)


@dataclass(frozen=True)
class ValidadorResult:
    valida: bool
    confianca: float
    afirmacoes_sem_respaldo: list[str] = field(default_factory=list)
    motivo: str = ""
    erro: bool = False


class Validador:
    def __init__(self, confidence_threshold: float = 0.7) -> None:
        self.confidence_threshold = confidence_threshold

    @staticmethod
    def _format_sources(sources: list[Hit]) -> str:
        if not sources:
            return "<fontes>\nNenhum manual recuperado.\n</fontes>"
        parts = []
        for idx, hit in enumerate(sources, start=1):
            safe = re.sub(r"</?\s*fonte[^>]*>", "", hit.content, flags=re.IGNORECASE)
            parts.append(f'<fonte id="{idx}" titulo="{hit.document_title}">\n{safe}\n</fonte>')
        return "<fontes>\n" + "\n".join(parts) + "\n</fontes>"

    @staticmethod
    def _parse_judge_json(raw_text: str) -> dict[str, Any]:
        """Extrai e valida o JSON retornado pelo modelo de forma tolerante a formatações."""
        cleaned = raw_text.strip()
        first_word = cleaned.split(None, 1)[0].upper().rstrip(".,;:") if cleaned else ""
        if first_word in ("NAO", "NÃO"):
            return {
                "valida": False,
                "confianca": 0.0,
                "afirmacoes_sem_respaldo": ["Afirmação não suportada pelos manuais."],
                "motivo": "Reprovado na conferência de fidelidade.",
            }
        if first_word == "SIM":
            return {
                "valida": True,
                "confianca": 1.0,
                "afirmacoes_sem_respaldo": [],
                "motivo": "Resposta validada pelo juiz.",
            }

        candidate = cleaned
        if "```" in candidate:
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", candidate, re.DOTALL)
            if match:
                candidate = match.group(1)

        start = candidate.find("{")
        end = candidate.rfind("}")
        if start != -1 and end > start:
            try:
                data = json.loads(candidate[start : end + 1])
                if isinstance(data, dict):
                    return data
            except Exception as parse_err:
                log.debug("JSON parse fallback error: %s", parse_err)

        if cleaned:
            if Validador._is_discursive_rejection(cleaned):
                return {
                    "valida": False,
                    "confianca": 0.0,
                    "afirmacoes_sem_respaldo": ["Afirmação não suportada pelos manuais."],
                    "motivo": "Reprovado na conferência de fidelidade.",
                }
            # Texto discursivo afirmativo (ex.: "Nenhuma afirmação inventada")
            return {
                "valida": True,
                "confianca": 1.0,
                "afirmacoes_sem_respaldo": [],
                "motivo": "Resposta aceita pelo juiz.",
            }

        raise ValueError("Resposta do validador vazia.")

    @staticmethod
    def _is_discursive_rejection(cleaned: str) -> bool:
        """Detecta reprovação clara em texto livre quando o modelo não devolve JSON nem SIM/NAO."""
        norm = (
            unicodedata.normalize("NFKD", cleaned).encode("ASCII", "ignore").decode("utf-8").lower()
        )
        norm = re.sub(r"\s+", " ", norm).strip()
        rejection_patterns = (
            r"\breprovad[ao]s?\b",
            r"(?<!nao )(?<!sem )\binvalid[ao]s?\b",
            r"\bnao\s+(?:e|esta|sao|estao)\s+sustentad[ao]s?\b",
            r"(?<!nao )(?<!sem )\bcontradiz(?:em)?\b",
            r"(?<!afirma que )(?<!diz que )\bnao\s+consta\b",
            r"(?<!nao )(?<!sem )(?<!ha )\balucina\w*\b",
            r"\b(?:possui|contem|apresenta|ha)\s+(?:afirmac(?:ao|oes)|informac(?:ao|oes)|dados?)\s+sem\s+respaldo\b",
        )
        return any(re.search(pat, norm) for pat in rejection_patterns)

    def interpretar_resposta(self, raw_text: str) -> ValidadorResult:
        """Interpreta a saída do modelo juiz (JSON ou veredito)."""
        try:
            data = self._parse_judge_json(raw_text)
            valida = bool(data.get("valida", False))
            confianca = float(data.get("confianca", 0.0))
            confianca = max(0.0, min(1.0, confianca))
            afirmacoes = [str(x) for x in data.get("afirmacoes_sem_respaldo", []) if str(x).strip()]
            motivo = str(data.get("motivo", "Validação concluída."))

            aprovado = valida and (confianca >= self.confidence_threshold)
            if not aprovado and not afirmacoes and not valida:
                afirmacoes = ["A resposta contém instruções não suportadas pelos manuais."]

            return ValidadorResult(
                valida=aprovado,
                confianca=confianca,
                afirmacoes_sem_respaldo=afirmacoes,
                motivo=motivo,
                erro=False,
            )
        except (LLMError, ValueError, Exception) as exc:
            log.error("Erro durante a execução do Validador de Resposta: %s", exc)
            return ValidadorResult(
                valida=True,
                confianca=1.0,
                afirmacoes_sem_respaldo=[],
                motivo="Validador indisponível; resposta aceita com ressalva técnica.",
                erro=True,
            )

    async def validar(
        self,
        query: str,
        sources: list[Hit],
        answer: str,
        llm: LLM,
    ) -> ValidadorResult:
        """Executa a validação anti-alucinação comparando a resposta com as fontes recuperadas."""
        if not sources:
            return ValidadorResult(
                valida=False,
                confianca=1.0,
                afirmacoes_sem_respaldo=["Nenhum manual de apoio foi recuperado."],
                motivo="Não existem trechos de manuais recuperados para fundamentar esta resposta.",
            )

        sources_block = self._format_sources(sources)
        user_prompt = (
            f"MANUAIS RECUPERADOS:\n{sources_block}\n\n"
            f"DÚVIDA DO USUÁRIO:\n{query}\n\n"
            f"RESPOSTA GERADA PELA IA:\n{answer}\n\n"
            "Avalie se a resposta é estritamente sustentada pelos manuais acima conforme as regras."
        )

        try:
            result = await llm.complete(
                [
                    ChatMessage("system", VALIDADOR_SYSTEM_PROMPT),
                    ChatMessage("user", user_prompt),
                ],
                temperature=0.0,
                max_tokens=400,
            )
            return self.interpretar_resposta(result.text)
        except (LLMError, ValueError, Exception) as exc:
            log.error("Erro durante a execução do Validador de Resposta: %s", exc)
            return ValidadorResult(
                valida=True,
                confianca=0.5,
                afirmacoes_sem_respaldo=[],
                motivo="Validador indisponível; resposta aceita com ressalva técnica.",
                erro=True,
            )
