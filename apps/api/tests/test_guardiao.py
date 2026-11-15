"""Testes automatizados do Agente 1: Guardião de Entrada."""

import pytest

from h2d.agents.guardiao import Guardiao
from h2d.llm.client import FakeLLM


@pytest.fixture
def guardiao() -> Guardiao:
    return Guardiao()


@pytest.mark.parametrize(
    "texto",
    [
        "Como configuro a impressora da sala de reunião?",
        "Esqueci minha senha do Windows, como faço?",
        "O monitor secundário não está dando vídeo",
        "Qual o procedimento para solicitar acesso à VPN?",
        "Preciso de ajuda com o Outlook que não abre",
    ],
)
def test_guardiao_clean_messages_pass(guardiao: Guardiao, texto: str) -> None:
    res = guardiao.check_fast(texto)
    assert res is None  # Camada rápida aprovou (sem termos impróprios)


@pytest.mark.parametrize(
    ("texto", "categoria_esperada"),
    [
        ("Que porra é essa que não funciona?", "palavrao"),
        ("Esse sistema é uma merda completa", "palavrao"),
        ("Vai se foder suporte inútil", "palavrao"),
        ("Seu filho da puta me ajuda logo", "palavrao"),
        ("Que caralho de erro é esse", "palavrao"),
        ("vsf suporte ruim", "palavrao"),
        ("esse cara é um arrombado", "palavrao"),
    ],
)
def test_guardiao_palavroes_explicit(
    guardiao: Guardiao, texto: str, categoria_esperada: str
) -> None:
    res = guardiao.check_fast(texto)
    assert res is not None
    assert res.aprovado is False
    assert res.categoria == categoria_esperada


@pytest.mark.parametrize(
    ("texto", "categoria_esperada"),
    [
        ("Seu macaco burro", "preconceito"),
        ("Esse atendente é um retardado mental", "preconceito"),
        ("Vou te matar se não resolver isso", "assedio"),
        ("Vou te quebrar na saída", "assedio"),
    ],
)
def test_guardiao_preconceito_e_assedio(
    guardiao: Guardiao, texto: str, categoria_esperada: str
) -> None:
    res = guardiao.check_fast(texto)
    assert res is not None
    assert res.aprovado is False
    assert res.categoria == categoria_esperada


@pytest.mark.parametrize(
    "texto_ofuscado",
    [
        "Que p0rr4 de computador é esse?",
        "Sistema de m3rd4",
        "p o r r a não aguento mais",
        "poooorrrraaaa travou de novo",
        "v@dia de máquina",
        "f0d4 esse sistema",
    ],
)
def test_guardiao_leet_speak_and_variations(guardiao: Guardiao, texto_ofuscado: str) -> None:
    res = guardiao.check_fast(texto_ofuscado)
    assert res is not None
    assert res.aprovado is False


@pytest.mark.parametrize(
    "termo_tecnico",
    [
        "Como usar o comando kill process no Linux?",
        "Preciso rodar kill -9 no processo que travou",
        "Como configurar a arquitetura master/slave no banco de dados?",
        "Qual o comando para abortar uma execução no terminal?",
        "Como gero um memory dump para analisar o crash?",
        "O daemon do Docker parou de responder, como reiniciar?",
    ],
)
def test_guardiao_technical_legitimate_terms_not_blocked(
    guardiao: Guardiao, termo_tecnico: str
) -> None:
    """Termos técnicos legítimos de TI NÃO devem ser confundidos com ofensas."""
    res = guardiao.check_fast(termo_tecnico)
    assert res is None  # Camada rápida não bloqueia termos técnicos


@pytest.mark.asyncio
async def test_guardiao_semantic_layer_catches_subtle_offense(guardiao: Guardiao) -> None:
    """Testa a camada semântica com FakeLLM para casos sutis."""

    def llm_handler(messages) -> str:
        prompt_content = messages[-1].content
        if "preconceito velado" in prompt_content:
            return (
                '{"aprovado": false, "categoria": "preconceito", "motivo": "Ironia detectada"}'
            )
        return '{"aprovado": true, "categoria": "ok", "motivo": "Pergunta legítima"}'

    fake_llm = FakeLLM(llm_handler)
    res_subtle = await guardiao.avaliar("Aqui tem preconceito velado", llm=fake_llm)
    assert res_subtle.aprovado is False
    assert res_subtle.categoria == "preconceito"
    assert res_subtle.camada == "semantica"

    res_clean = await guardiao.avaliar("Como troco a senha do email?", llm=fake_llm)
    assert res_clean.aprovado is True
    assert res_clean.categoria == "ok"
