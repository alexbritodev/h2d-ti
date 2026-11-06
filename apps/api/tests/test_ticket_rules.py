import uuid
from datetime import UTC, datetime, timedelta

import pytest

from h2d.models import Level, Priority
from h2d.tickets.rules import (
    Candidate,
    in_schedule,
    priority_from,
    route,
    sla_due,
    sla_state,
)

H, M, L = Level.HIGH, Level.MEDIUM, Level.LOW
# Quinta-feira, 10h no horário de Brasília (UTC-3).
QUINTA_10H = datetime(2026, 11, 5, 13, 0, tzinfo=UTC)
REDES = uuid.uuid4()
IMPRESSORA = uuid.uuid4()


@pytest.mark.parametrize(
    ("impacto", "urgencia", "esperada"),
    [
        (H, H, Priority.P1), (H, M, Priority.P2), (H, L, Priority.P3),
        (M, H, Priority.P2), (M, M, Priority.P3), (M, L, Priority.P4),
        (L, H, Priority.P3), (L, M, Priority.P4), (L, L, Priority.P4),
    ],
)  # fmt: skip
def test_matriz_de_prioridade(impacto, urgencia, esperada):
    assert priority_from(impacto, urgencia) is esperada


def test_prazo_e_estado_do_sla():
    criado = datetime(2026, 11, 5, 9, 0, tzinfo=UTC)
    prazo = sla_due(criado, 240)

    assert prazo == criado + timedelta(hours=4)
    assert sla_state(created_at=criado, due=prazo, now=criado + timedelta(hours=1)) == "ok"
    assert sla_state(created_at=criado, due=prazo, now=criado + timedelta(hours=3)) == "at_risk"
    assert sla_state(created_at=criado, due=prazo, now=prazo) == "breached"
    assert sla_state(created_at=criado, due=None, now=prazo) == "ok"
    assert (
        sla_state(created_at=criado, due=prazo, now=prazo, done_at=prazo - timedelta(minutes=1))
        == "met"
    )
    assert (
        sla_state(created_at=criado, due=prazo, now=prazo, done_at=prazo + timedelta(minutes=1))
        == "breached"
    )


def _tec(
    skills=(REDES,), disponivel=True, capacidade=10, abertos=0, peso=0, agenda=None, ultimo=None
):
    return Candidate(
        technician_id=uuid.uuid4(),
        skill_ids=frozenset(skills),
        is_available=disponivel,
        max_capacity=capacidade,
        open_count=abertos,
        open_weight=peso,
        schedule=agenda or {},
        last_assigned_at=ultimo,
    )


def _rotear(candidatos, **kw):
    base = {
        "required_skill_id": REDES,
        "priority": Priority.P2,
        "confidence": 0.9,
        "threshold": 0.6,
        "now": QUINTA_10H,
    }
    return route(candidatos, **{**base, **kw})


def test_escolhe_o_tecnico_com_menor_carga_ponderada_e_explica_o_motivo():
    leve = _tec(abertos=5, peso=5)  # muitos chamados, mas de pouco peso
    pesado = _tec(abertos=2, peso=16)  # poucos chamados, mas dois P1

    decisao = _rotear([pesado, leve])

    assert decisao.technician_id == leve.technician_id
    assert decisao.manual_triage is False
    assert "carga ponderada (5)" in decisao.reason


def test_empate_vai_para_quem_recebeu_ha_mais_tempo():
    antigo = _tec(peso=4, ultimo=QUINTA_10H - timedelta(days=2))
    recente = _tec(peso=4, ultimo=QUINTA_10H - timedelta(hours=1))
    nunca = _tec(peso=4, ultimo=None)

    assert _rotear([recente, antigo, nunca]).technician_id == nunca.technician_id
    decisao = _rotear([recente, antigo])
    assert decisao.technician_id == antigo.technician_id
    assert "rodízio" in decisao.reason


def test_resultado_e_sempre_o_mesmo_para_os_mesmos_dados():
    candidatos = [_tec(peso=3) for _ in range(5)]

    escolhas = {_rotear(list(reversed(candidatos))).technician_id for _ in range(3)}
    escolhas |= {_rotear(candidatos).technician_id}

    assert len(escolhas) == 1


@pytest.mark.parametrize(
    ("candidatos", "trecho_do_motivo"),
    [
        ([], "habilidade necessária"),
        ([_tec(skills=(IMPRESSORA,))], "habilidade necessária"),
        ([_tec(disponivel=False)], "indisponíveis"),
        ([_tec(capacidade=2, abertos=2)], "capacidade cheia"),
        ([_tec(agenda={"mon": ["08:00", "18:00"]})], "horário"),
    ],
)
def test_sem_ninguem_elegivel_vai_para_a_triagem_manual(candidatos, trecho_do_motivo):
    decisao = _rotear(candidatos)

    assert decisao.technician_id is None
    assert decisao.manual_triage is True
    assert trecho_do_motivo in decisao.reason


def test_confianca_baixa_ou_sem_classificacao_vai_para_a_triagem_manual():
    tecnico = _tec()

    baixa = _rotear([tecnico], confidence=0.4)
    sem = _rotear([tecnico], confidence=None, priority=None)

    assert baixa.manual_triage and "abaixo do limiar" in baixa.reason
    assert sem.manual_triage and "sem classificação" in sem.reason


def test_p1_avisa_o_lider_mesmo_na_triagem():
    assert _rotear([_tec()], priority=Priority.P1).notify_leader is True
    assert _rotear([], priority=Priority.P1).notify_leader is True
    assert _rotear([_tec()], priority=Priority.P3).notify_leader is False


def test_agenda_respeita_dia_hora_e_fuso():
    agenda = {"thu": ["08:00", "18:00"]}

    assert in_schedule(agenda, QUINTA_10H, "America/Sao_Paulo") is True
    # 22h em Brasília: fora do expediente.
    assert in_schedule(agenda, QUINTA_10H + timedelta(hours=12), "America/Sao_Paulo") is False
    # Sexta não tem entrada na agenda: folga.
    assert in_schedule(agenda, QUINTA_10H + timedelta(days=1), "America/Sao_Paulo") is False
    assert in_schedule({}, QUINTA_10H, "America/Sao_Paulo") is True
