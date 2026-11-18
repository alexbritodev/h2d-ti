"""Testes automatizados do Agente 2: Validador de Resposta (anti-alucinação)."""

import uuid

import pytest

from h2d.agents.validador import Validador
from h2d.kb.search import Hit
from h2d.llm.client import FakeLLM, LLMError


def _make_sample_hit(content: str, title: str = "Manual VPN") -> Hit:
    return Hit(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_title=title,
        breadcrumb="Redes > VPN",
        content=content,
        visibility="public",
        score=0.9,
        kind="kb",
    )


@pytest.mark.asyncio
async def test_validador_grounded_answer_approved() -> None:
    hit = _make_sample_hit("A sessão da VPN expira após 12 horas ininterruptas.")
    validador = Validador(confidence_threshold=0.7)

    def llm_handler(_messages) -> str:
        return """{
            "valida": true,
            "confianca": 0.95,
            "afirmacoes_sem_respaldo": [],
            "motivo": "Todas as informações sobre 12 horas constam no manual da VPN [1]."
        }"""

    fake_llm = FakeLLM(llm_handler)
    res = await validador.validar(
        query="Quanto tempo dura a VPN?",
        sources=[hit],
        answer="A sessão da VPN corporativa dura 12 horas [1].",
        llm=fake_llm,
    )

    assert res.valida is True
    assert res.confianca >= 0.7
    assert len(res.afirmacoes_sem_respaldo) == 0


@pytest.mark.asyncio
async def test_validador_invented_answer_rejected() -> None:
    hit = _make_sample_hit("Para resetar a senha, acesse o portal https://portal.h2d.local.")
    validador = Validador(confidence_threshold=0.7)

    def llm_handler(_messages) -> str:
        return """{
            "valida": false,
            "confianca": 0.2,
            "afirmacoes_sem_respaldo": ["Baixe o aplicativo AnyDesk."],
            "motivo": "O manual apenas orienta acessar o portal; menção ao AnyDesk é inventada."
        }"""

    fake_llm = FakeLLM(llm_handler)
    res = await validador.validar(
        query="Como resetar a senha?",
        sources=[hit],
        answer="Acesse o portal e baixe o aplicativo AnyDesk para o técnico conectar.",
        llm=fake_llm,
    )

    assert res.valida is False
    assert len(res.afirmacoes_sem_respaldo) > 0
    assert "AnyDesk" in res.afirmacoes_sem_respaldo[0]


@pytest.mark.asyncio
async def test_validador_empty_sources_rejected() -> None:
    validador = Validador()
    fake_llm = FakeLLM()
    res = await validador.validar(
        query="Como funciona o sistema X?",
        sources=[],
        answer="O sistema X funciona assim.",
        llm=fake_llm,
    )
    assert res.valida is False
    assert "manuais" in res.motivo.lower()


@pytest.mark.asyncio
async def test_validador_robust_json_parsing() -> None:
    hit = _make_sample_hit("Texto base")
    validador = Validador()

    # Resposta envolvida em markdown code fence e texto antes/depois
    def llm_handler(_messages) -> str:
        return """Aqui está a análise:
```json
{
  "valida": true,
  "confianca": 0.88,
  "afirmacoes_sem_respaldo": [],
  "motivo": "Sustentado pelos trechos"
}
```
Fim da validação."""

    fake_llm = FakeLLM(llm_handler)
    res = await validador.validar(
        query="Pergunta",
        sources=[hit],
        answer="Resposta",
        llm=fake_llm,
    )
    assert res.valida is True
    assert res.confianca == 0.88


@pytest.mark.asyncio
async def test_validador_llm_error_fallback_resilient() -> None:
    hit = _make_sample_hit("Texto base")
    validador = Validador()

    class FailingLLM:
        model_name = "failing"

        async def complete(self, *_args, **_kwargs):
            raise LLMError("Timeout ao falar com o modelo validador")

    res = await validador.validar(
        query="Pergunta",
        sources=[hit],
        answer="Resposta técnica com fonte [1]",
        llm=FailingLLM(),  # type: ignore[arg-type]
    )
    # Validador não derruba o sistema
    assert res.erro is True
    assert "indisponível" in res.motivo


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("Resposta reprovada pois contradiz o manual.", False),
        ("A resposta é inválida e não é sustentada pelas fontes.", False),
        ("Possui dados sem respaldo nos manuais.", False),
        ("Nenhuma afirmação inventada.", True),
        ("Nenhuma afirmação sem respaldo encontrada.", True),
    ],
)
def test_validador_discursive_fallback_distinguishes_rejection(texto: str, esperado: bool) -> None:
    validador = Validador(confidence_threshold=0.7)
    res = validador.interpretar_resposta(texto)
    assert res.valida is esperado


def test_validador_parses_json_with_braces_in_linux_commands() -> None:
    validador = Validador(confidence_threshold=0.7)
    raw = """```json
{
  "valida": false,
  "confianca": 0.2,
  "afirmacoes_sem_respaldo": ["find /var -exec rm {} \\;"],
  "motivo": "O comando {rm} não consta no manual."
}
```"""
    res = validador.interpretar_resposta(raw)
    assert res.valida is False
    assert res.afirmacoes_sem_respaldo == ["find /var -exec rm {} \\;"]


def test_validador_parses_truncated_json_and_percentage_variants() -> None:
    validador = Validador(confidence_threshold=0.7)
    truncated = '{"valida": true, "confianca": 0.92, "motivo": "Comandos df -h e du constam'
    res_trunc = validador.interpretar_resposta(truncated)
    assert res_trunc.valida is True
    assert res_trunc.confianca == 0.92

    variants = '{"válida": "sim", "confiança": 95, "motivo": "Tudo ok"}'
    res_var = validador.interpretar_resposta(variants)
    assert res_var.valida is True
    assert res_var.confianca == 0.95
