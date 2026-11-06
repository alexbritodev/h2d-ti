"""Rotas que o n8n chama na API, pela rede interna do Docker (o Caddy do web responde 404 a elas).

Cada pedido traz X-H2D-Timestamp e X-H2D-Signature (HMAC do horário e do corpo). Sem assinatura
válida a resposta é 401, e sem segredo configurado as rotas ficam desligadas (503).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from h2d.config import get_settings
from h2d.deps import SessionDep
from h2d.outbox import verify
from h2d.tickets.sla_watch import emit_sla_alerts


async def verified_n8n(
    request: Request,
    x_h2d_timestamp: Annotated[str | None, Header()] = None,
    x_h2d_signature: Annotated[str | None, Header()] = None,
) -> bytes:
    secret = get_settings().n8n_hmac_secret
    if secret is None or not secret.get_secret_value():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Integração com o n8n desligada")
    body = await request.body()
    valid = bool(x_h2d_timestamp and x_h2d_signature) and verify(
        secret.get_secret_value(), x_h2d_timestamp or "", body, x_h2d_signature or ""
    )
    if not valid:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Assinatura inválida")
    return body


router = APIRouter(prefix="/hooks/n8n", tags=["hooks"], dependencies=[Depends(verified_n8n)])


@router.post("/ping", operation_id="n8nPing")
async def ping() -> dict[str, bool]:
    return {"ok": True}


@router.post("/sla-check", operation_id="n8nSlaCheck")
async def sla_check(session: SessionDep) -> dict[str, object]:
    """Chamado pelo vigia de SLA do n8n (a cada poucos minutos). Cada alerta nasce uma vez só."""
    alerts = await emit_sla_alerts(session)
    await session.commit()
    return {"alerts": alerts}
