import json

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from h2d.llm.client import LLMError
from h2d.models import (
    Category,
    LlmCall,
    OutboxEvent,
    Priority,
    Role,
    Skill,
    SlaPolicy,
    SlaTarget,
    Technician,
    TechnicianSkill,
    Ticket,
    TicketEvent,
    TicketStatus,
)
from tests.conftest import PASSWORD


async def _catalog(session: AsyncSession, make_user) -> dict:
    skill = Skill(name="redes-vpn")
    policy = SlaPolicy(name="Padrão")
    session.add_all([skill, policy])
    await session.flush()
    session.add_all(
        SlaTarget(
            policy_id=policy.id, priority=p, first_response_minutes=30, resolution_minutes=240
        )
        for p in Priority
    )
    parent = Category(name="Rede e VPN", default_skill_id=skill.id, sla_policy_id=policy.id)
    session.add(parent)
    await session.flush()
    session.add(Category(name="VPN", parent_id=parent.id, default_skill_id=skill.id))
    tech_user = await make_user(email="tec@h2d.local", role=Role.TECH)
    tech = Technician(user_id=tech_user.id, max_capacity=10, is_available=True)
    session.add(tech)
    await session.flush()
    session.add(TechnicianSkill(technician_id=tech.id, skill_id=skill.id))
    await session.flush()
    return {"tech": tech, "tech_user": tech_user, "category": parent}


def _classification(**over) -> str:
    base = {
        "categoria": "Rede e VPN",
        "subcategoria": "VPN",
        "impacto": "alto",
        "urgencia": "alto",
        "resumo": "VPN não conecta para o setor inteiro.",
        "ja_tentado": "Usuário reiniciou o cliente.",
        "habilidades": ["redes-vpn"],
        "confianca": 0.9,
        "motivo": "erro de VPN",
    }
    return json.dumps({**base, **over}, ensure_ascii=False)


def _use_classification(app, text: str) -> None:
    def handler(messages) -> str:
        if "classifica chamados" in messages[0].content:
            return text
        return "Resposta de teste [1]."

    app.state.fake_llm._handler = handler


async def _login(client, make_user, role=Role.USER, email="pessoa@h2d.local"):
    user = await make_user(email=email, role=role)
    response = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200
    return user


async def _relogin(client, email: str) -> None:
    client.cookies.clear()
    response = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200


async def _escalate(client, text="A VPN não conecta e o setor está parado") -> dict:
    conversation = (await client.post("/api/chat/conversations")).json()["id"]
    sent = await client.post(
        f"/api/chat/conversations/{conversation}/messages", json={"content": text}
    )
    assert sent.status_code == 200
    response = await client.post(f"/api/chat/conversations/{conversation}/escalate")
    assert response.status_code == 200
    return response.json()


async def test_escalonar_abre_chamado_classificado_com_prioridade_da_matriz_e_atribuido(
    client, make_user, session, app
):
    catalog = await _catalog(session, make_user)
    _use_classification(app, _classification())
    await _login(client, make_user)

    ref = await _escalate(client)

    ticket = await session.get_one(Ticket, ref["id"])
    assert ref["code"].startswith("H2D-")
    # Impacto alto + urgência alta = P1, pela matriz (o modelo não escolhe a prioridade).
    assert ticket.priority is Priority.P1
    assert ticket.status is TicketStatus.ASSIGNED
    assert ticket.technician_id == catalog["tech"].id
    assert ticket.first_response_due and ticket.resolution_due
    assert ticket.already_tried == "Usuário reiniciou o cliente."
    events = list(await session.scalars(select(TicketEvent).order_by(TicketEvent.created_at)))
    assert [e.type for e in events] == ["created", "classified", "assigned", "escalated"]
    assigned = next(e for e in events if e.type == "assigned")
    assert "carga ponderada" in (assigned.reason or "")
    outbox = list(await session.scalars(select(OutboxEvent)))
    assert [o.type for o in outbox] == ["ticket.created"]
    assert outbox[0].payload["notify_leader"] is True
    assert outbox[0].payload["assignee"]["email"] == "tec@h2d.local"
    purposes = [c.purpose for c in await session.scalars(select(LlmCall))]
    assert "classify" in purposes


async def test_escalar_duas_vezes_nao_duplica_o_chamado(client, make_user, session, app):
    await _catalog(session, make_user)
    _use_classification(app, _classification())
    await _login(client, make_user)
    conversation = (await client.post("/api/chat/conversations")).json()["id"]

    first = (await client.post(f"/api/chat/conversations/{conversation}/escalate")).json()
    second = (await client.post(f"/api/chat/conversations/{conversation}/escalate")).json()

    assert first["id"] == second["id"]
    assert len(list(await session.scalars(select(Ticket)))) == 1


@pytest.mark.parametrize(
    ("resposta", "trecho_do_motivo"),
    [
        (_classification(confianca=0.3), "abaixo do limiar"),
        (_classification(categoria="Churrasco"), "fora da lista"),
        ("isto não é JSON", "classificação inválida"),
    ],
)
async def test_classificacao_fraca_ou_invalida_vai_para_a_triagem_manual(
    client, make_user, session, app, resposta, trecho_do_motivo
):
    await _catalog(session, make_user)
    _use_classification(app, resposta)
    await _login(client, make_user)

    ref = await _escalate(client)

    ticket = await session.get_one(Ticket, ref["id"])
    assert ticket.status is TicketStatus.TRIAGE and ticket.technician_id is None
    motivos = " ".join(e.reason or "" for e in await session.scalars(select(TicketEvent)))
    assert trecho_do_motivo in motivos


async def test_modelo_fora_do_ar_ainda_abre_o_chamado_sem_classificar(
    client, make_user, session, app
):
    await _catalog(session, make_user)
    _use_classification(app, _classification())
    await _login(client, make_user)
    conversation = (await client.post("/api/chat/conversations")).json()["id"]
    await client.post(
        f"/api/chat/conversations/{conversation}/messages", json={"content": "meu e-mail não abre"}
    )

    async def falha(messages, **kwargs):
        raise LLMError("HTTP 503")

    app.state.fake_llm.complete = falha
    response = await client.post(f"/api/chat/conversations/{conversation}/escalate")

    assert response.status_code == 200
    ticket = await session.get_one(Ticket, response.json()["id"])
    assert ticket.status is TicketStatus.TRIAGE
    assert ticket.priority is None and ticket.classification is None
    assert ticket.summary == "meu e-mail não abre"


async def test_tema_critico_abre_o_chamado_na_propria_resposta(client, make_user, session, app):
    await _catalog(session, make_user)
    _use_classification(app, _classification())
    await _login(client, make_user)
    conversation = (await client.post("/api/chat/conversations")).json()["id"]

    response = await client.post(
        f"/api/chat/conversations/{conversation}/messages",
        json={"content": "recebi um ransomware, os arquivos sumiram"},
    )

    events = [
        json.loads(b.splitlines()[1].removeprefix("data: "))
        for b in response.text.strip().split("\n\n")
    ]
    done = events[-1]
    assert done["action"] == "escalate" and done["ticket"]["code"].startswith("H2D-")


async def test_usuario_so_ve_os_proprios_chamados_e_a_ti_ve_todos(client, make_user, session, app):
    await _catalog(session, make_user)
    _use_classification(app, _classification())
    await _login(client, make_user, email="ana@h2d.local")
    ana = await _escalate(client)
    await _relogin(client, "tec@h2d.local")  # técnico criado pelo catálogo
    await _login(client, make_user, email="bia@h2d.local")
    bia = await _escalate(client)

    como_bia = (await client.get("/api/tickets")).json()
    assert [t["id"] for t in como_bia] == [bia["id"]]
    assert (await client.get(f"/api/tickets/{ana['id']}")).status_code == 404

    await _relogin(client, "tec@h2d.local")
    como_ti = (await client.get("/api/tickets")).json()
    assert {t["id"] for t in como_ti} == {ana["id"], bia["id"]}
    detalhe = (await client.get(f"/api/tickets/{ana['id']}")).json()
    assert detalhe["events"][0]["type"] == "created"
    assert detalhe["sla"]["state"] == "ok"


async def test_fila_vem_ordenada_por_prioridade(client, make_user, session, app):
    await _catalog(session, make_user)
    await _login(client, make_user, email="ana@h2d.local")
    _use_classification(app, _classification(impacto="baixo", urgencia="baixo"))
    baixa = await _escalate(client)
    _use_classification(app, _classification())
    alta = await _escalate(client)
    await _relogin(client, "tec@h2d.local")

    fila = (await client.get("/api/tickets")).json()

    assert [t["id"] for t in fila] == [alta["id"], baixa["id"]]
    assert [t["priority"] for t in fila] == ["P1", "P4"]


async def test_tecnico_mexe_so_no_proprio_chamado_e_o_andamento_marca_a_primeira_resposta(
    client, make_user, session, app
):
    catalog = await _catalog(session, make_user)
    _use_classification(app, _classification())
    await _login(client, make_user, email="ana@h2d.local")
    ref = await _escalate(client)
    outro = await make_user(email="outro-tec@h2d.local", role=Role.TECH)
    session.add(Technician(user_id=outro.id))
    await session.flush()

    await _relogin(client, "outro-tec@h2d.local")
    negado = await client.patch(f"/api/tickets/{ref['id']}", json={"status": "in_progress"})
    assert negado.status_code == 403

    await _relogin(client, catalog["tech_user"].email)
    ok = await client.patch(f"/api/tickets/{ref['id']}", json={"status": "in_progress"})
    assert ok.status_code == 200 and ok.json()["status"] == "in_progress"
    ticket = await session.get_one(Ticket, ref["id"])
    await session.refresh(ticket)
    assert ticket.first_response_at is not None
    reatribuir = await client.patch(
        f"/api/tickets/{ref['id']}", json={"technician_id": str(catalog["tech"].id)}
    )
    assert reatribuir.status_code == 403
    encerrar = await client.patch(f"/api/tickets/{ref['id']}", json={"status": "resolved"})
    assert encerrar.status_code == 422


async def test_admin_trata_a_triagem_manual_reatribuindo_com_motivo(
    client, make_user, session, app
):
    catalog = await _catalog(session, make_user)
    _use_classification(app, _classification(confianca=0.2))
    await _login(client, make_user, email="ana@h2d.local")
    ref = await _escalate(client)
    await _login(client, make_user, Role.ADMIN, "chefe@h2d.local")

    fila = (await client.get("/api/tickets", params={"triage": "true"})).json()
    assert [t["id"] for t in fila] == [ref["id"]]

    response = await client.patch(
        f"/api/tickets/{ref['id']}",
        json={"technician_id": str(catalog["tech"].id), "reason": "É assunto de redes"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "assigned"
    motivos = [
        e.reason
        for e in await session.scalars(select(TicketEvent).where(TicketEvent.type == "assigned"))
    ]
    assert "É assunto de redes" in motivos
    assert "ticket.assigned" in [o.type for o in await session.scalars(select(OutboxEvent))]


async def test_resolver_exige_solucao_grava_o_prazo_e_nao_reabre(client, make_user, session, app):
    catalog = await _catalog(session, make_user)
    _use_classification(app, _classification())
    await _login(client, make_user, email="ana@h2d.local")
    ref = await _escalate(client)
    await _relogin(client, catalog["tech_user"].email)

    vazio = await client.post(f"/api/tickets/{ref['id']}/resolve", json={"solution": ""})
    resolvido = await client.post(
        f"/api/tickets/{ref['id']}/resolve", json={"solution": "Reinstalei o cliente da VPN."}
    )
    de_novo = await client.post(
        f"/api/tickets/{ref['id']}/resolve", json={"solution": "Outra solução qualquer"}
    )

    assert vazio.status_code == 422
    assert resolvido.json()["status"] == "resolved"
    assert resolvido.json()["sla"]["state"] == "met"
    assert de_novo.status_code == 409
    detalhe = (await client.get(f"/api/tickets/{ref['id']}")).json()
    assert detalhe["solution"] == "Reinstalei o cliente da VPN."
    assert "ticket.resolved" in [o.type for o in await session.scalars(select(OutboxEvent))]


async def test_comentarios_so_do_solicitante_e_da_ti(client, make_user, session, app):
    catalog = await _catalog(session, make_user)
    _use_classification(app, _classification())
    await _login(client, make_user, email="ana@h2d.local")
    ref = await _escalate(client)

    dono = await client.post(
        f"/api/tickets/{ref['id']}/comments", json={"text": "Ainda sem acesso"}
    )
    assert dono.status_code == 201

    await _login(client, make_user, email="curiosa@h2d.local")
    assert (
        await client.post(f"/api/tickets/{ref['id']}/comments", json={"text": "oi"})
    ).status_code == 404

    await _relogin(client, catalog["tech_user"].email)
    ti = await client.post(f"/api/tickets/{ref['id']}/comments", json={"text": "Estou olhando"})
    assert ti.status_code == 201
    ticket = await session.get_one(Ticket, ref["id"])
    await session.refresh(ticket)
    assert ticket.first_response_at is not None


async def test_sem_login_nao_ve_chamados(client):
    assert (await client.get("/api/tickets")).status_code == 401


async def test_lista_de_tecnicos_mostra_carga_e_habilidades_so_para_a_ti(
    client, make_user, session, app
):
    catalog = await _catalog(session, make_user)
    _use_classification(app, _classification())
    await _login(client, make_user, email="ana@h2d.local")
    assert (await client.get("/api/tickets/technicians")).status_code == 403
    await _escalate(client)
    await _relogin(client, catalog["tech_user"].email)

    tecnicos = (await client.get("/api/tickets/technicians")).json()

    assert [(t["open_tickets"], t["skills"]) for t in tecnicos] == [(1, ["redes-vpn"])]
