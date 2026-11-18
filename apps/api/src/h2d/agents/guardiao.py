"""Agente 1: Guardião de Entrada (filtro de conteúdo).

Analisa a mensagem do usuário antes de ela chegar ao RAG e à LLM principal,
bloqueando termos impróprios, ofensas, preconceito e assédio com estratégia em duas camadas:
1. Camada rápida: normalização de texto + regex configurável em JSON.
2. Camada semântica: classificação via LLM para casos sutis ou implícitos.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from h2d.llm.client import LLM, ChatMessage, LLMError, parse_json_object

log = logging.getLogger("h2d.agents.guardiao")

CategoriaBloqueio = Literal["ok", "palavrao", "preconceito", "assedio", "outro"]

GUARDIAO_BLOCKED_MESSAGE = (
    "Não foi possível processar sua mensagem pois identificamos conteúdos ou termos "
    "que não estão de acordo com as nossas diretrizes de uso. Por favor, reformule sua dúvida "
    "de TI de forma respeitosa para que possamos ajudá-lo."
)

GUARDIAO_SYSTEM_PROMPT = """Você é o Agente Guardião de Entrada de um suporte de TI corporativo.
Sua única responsabilidade é analisar a mensagem do usuário e detectar conteúdo impróprio.

Categorias:
1. "palavrao": Palavrões, xingamentos pesados e ofensas diretas.
2. "preconceito": Discurso de ódio, racismo, homofobia, xenofobia, machismo, capacitismo etc.
3. "assedio": Assédio sexual, assédio moral severo, ameaças físicas ou violência.
4. "outro": Outros conteúdos manifestamente abusivos não cobertos acima.
5. "ok": Mensagem apropriada para um canal de atendimento de TI.

IMPORTANTE:
- Termos técnicos de TI (ex.: "kill process", "master/slave", "abortar execução", "dump") \
NÃO são ofensas e DEVEM SER APROVADOS ("ok").
- Frustração moderada com problemas de TI sem ofensas dirigidas DEVE SER APROVADA ("ok").
- Responda OBRIGATORIAMENTE em JSON estrito com o seguinte formato:
{
  "aprovado": true ou false,
  "categoria": "ok" | "palavrao" | "preconceito" | "assedio" | "outro",
  "motivo": "Explicação concisa e objetiva da decisão"
}"""


@dataclass(frozen=True)
class GuardiaoResult:
    aprovado: bool
    categoria: CategoriaBloqueio
    motivo: str
    camada: Literal["rapida", "semantica", "bypass"] = "rapida"


class Guardiao:
    def __init__(self, terms_path: Path | str | None = None) -> None:
        if terms_path is None:
            terms_path = Path(__file__).resolve().parent / "guardiao_terms.json"
        self.terms_path = Path(terms_path)
        self._load_terms()

    def _load_terms(self) -> None:
        try:
            with open(self.terms_path, encoding="utf-8") as f:
                data = json.load(f)
            self.palavroes: list[str] = [
                self._normalize_basic(t) for t in data.get("palavroes", [])
            ]
            self.preconceito: list[str] = [
                self._normalize_basic(t) for t in data.get("preconceito", [])
            ]
            self.assedio: list[str] = [self._normalize_basic(t) for t in data.get("assedio", [])]
            self.whitelist_tecnica: list[str] = [
                self._normalize_basic(t) for t in data.get("whitelist_tecnica", [])
            ]
        except Exception as exc:
            log.error("Erro ao carregar termos do guardião em %s: %s", self.terms_path, exc)
            self.palavroes = []
            self.preconceito = []
            self.assedio = []
            self.whitelist_tecnica = []

    @staticmethod
    def _normalize_basic(text: str) -> str:
        """Remove acentos e passa para minúsculas."""
        normalized = unicodedata.normalize("NFKD", text)
        ascii_text = normalized.encode("ASCII", "ignore").decode("utf-8")
        return ascii_text.lower().strip()

    def normalize(self, text: str) -> str:
        """Normalização avançada para detectar variações, leet speak e espaçamentos artificiais."""
        clean = self._normalize_basic(text)

        leet_map = {
            "0": "o",
            "1": "i",
            "!": "i",
            "|": "i",
            "3": "e",
            "4": "a",
            "@": "a",
            "5": "s",
            "$": "s",
            "7": "t",
            "8": "b",
        }
        for char, replacement in leet_map.items():
            clean = clean.replace(char, replacement)

        prev = ""
        while prev != clean:
            prev = clean
            clean = re.sub(r"(?<=\b\w)\s+(?=\w\b)", "", clean)

        # Reduz repetições mantendo até 2 para 'r' e 's' e 1 para as demais
        clean = re.sub(
            r"([a-z])\1+",
            lambda m: m.group(1) * 2 if m.group(1) in ("r", "s") else m.group(1),
            clean,
        )
        return clean

    def check_fast(self, text: str) -> GuardiaoResult | None:
        """Camada rápida: checagem por lista de termos e regex."""
        norm_text = self.normalize(text)
        basic_text = self._normalize_basic(text)
        collapsed_single = re.sub(r"([a-z])\1+", r"\1", norm_text)

        is_whitelisted = False
        for tech in self.whitelist_tecnica:
            pattern = rf"\b{re.escape(tech)}\b"
            if (
                re.search(pattern, norm_text)
                or re.search(pattern, basic_text)
                or re.search(pattern, collapsed_single)
            ):
                is_whitelisted = True
                break

        checks: list[tuple[CategoriaBloqueio, list[str]]] = [
            ("assedio", self.assedio),
            ("preconceito", self.preconceito),
            ("palavrao", self.palavroes),
        ]

        for categoria, termos in checks:
            for termo in termos:
                if is_whitelisted and termo in ("kill", "abort", "slave", "master"):
                    continue

                pattern = rf"\b{re.escape(termo)}\b"
                termo_single = re.sub(r"([a-z])\1+", r"\1", termo)
                pattern_single = rf"\b{re.escape(termo_single)}\b"

                if (
                    re.search(pattern, norm_text)
                    or re.search(pattern, basic_text)
                    or re.search(pattern, collapsed_single)
                    or re.search(pattern_single, collapsed_single)
                ):
                    log.warning(
                        "Guardião (rápido) bloqueou mensagem. Categoria: %s, Termo: %s",
                        categoria,
                        termo,
                    )
                    return GuardiaoResult(
                        aprovado=False,
                        categoria=categoria,
                        motivo=f"Linguagem inadequada detectada ({categoria}).",
                        camada="rapida",
                    )

        return None

    @staticmethod
    def parse_semantic_response(raw_text: str) -> GuardiaoResult:
        """Interpreta o JSON retornado pela camada semântica com fail-open em erro de formato."""
        try:
            parsed = parse_json_object(raw_text.strip())
            aprovado = bool(parsed.get("aprovado", True))
            categoria = parsed.get("categoria", "ok" if aprovado else "outro")
            motivo = str(parsed.get("motivo", "Aprovado na análise semântica."))

            if categoria not in ("ok", "palavrao", "preconceito", "assedio", "outro"):
                categoria = "ok" if aprovado else "outro"

            if not aprovado:
                log.warning(
                    "Guardião (semântico) reprovou: categoria=%s motivo=%s",
                    categoria,
                    motivo,
                )

            return GuardiaoResult(
                aprovado=aprovado,
                categoria=categoria,  # type: ignore[arg-type]
                motivo=motivo,
                camada="semantica",
            )
        except (ValueError, Exception) as exc:
            log.warning("Guardião semântico indisponível (%s). Permitindo com base na rápida.", exc)
            return GuardiaoResult(
                aprovado=True,
                categoria="ok",
                motivo="Aprovado pela camada rápida (camada semântica indisponível).",
                camada="rapida",
            )

    async def check_semantic(
        self,
        text: str,
        llm: LLM,
    ) -> GuardiaoResult:
        """Camada semântica: chamada à LLM para detectar ironia ou preconceito velado."""
        try:
            result = await llm.complete(
                [
                    ChatMessage("system", GUARDIAO_SYSTEM_PROMPT),
                    ChatMessage("user", f"Analise a mensagem a seguir:\n\n{text}"),
                ],
                temperature=0.0,
                max_tokens=250,
            )
            return self.parse_semantic_response(result.text)
        except (LLMError, ValueError, Exception) as exc:
            log.warning("Guardião semântico indisponível (%s). Permitindo com base na rápida.", exc)
            return GuardiaoResult(
                aprovado=True,
                categoria="ok",
                motivo="Aprovado pela camada rápida (camada semântica indisponível).",
                camada="rapida",
            )

    async def avaliar(
        self,
        text: str,
        llm: LLM | None = None,
        *,
        fast_only: bool = False,
    ) -> GuardiaoResult:
        """Avalia a mensagem executando a camada rápida e, se necessário, a semântica."""
        fast_res = self.check_fast(text)
        if fast_res is not None:
            return fast_res

        if fast_only or llm is None:
            return GuardiaoResult(
                aprovado=True,
                categoria="ok",
                motivo="Aprovado na verificação de termos rápidos.",
                camada="rapida",
            )

        return await self.check_semantic(text, llm)
