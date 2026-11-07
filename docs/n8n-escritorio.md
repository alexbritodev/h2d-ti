# n8n: enviar eventos ao Escritório virtual

Os workflows existentes **não foram alterados**. Se o n8n participa do atendimento (por exemplo, o
aviso por e-mail do `01-aviso-de-chamado`), dá para fazê-lo aparecer no escritório acrescentando
manualmente dois nós ao fim do fluxo: ligue a saída de **Registrar como processado** aos dois nós
novos, em paralelo ao **Responder 200** (assim o escritório nunca atrasa nem derruba a resposta ao
outbox da API).

O webhook usa a mesma assinatura HMAC das outras rotas (`X-H2D-Timestamp` e `X-H2D-Signature`,
com o segredo `H2D_HMAC_SECRET` do n8n, igual ao `N8N_HMAC_SECRET` da API). Ele só é alcançável
pela rede interna do Docker: o Caddy do web responde 404 a `/api/hooks/*`.

## Nó 1: Code, "Assinar evento do escritório"

```javascript
// Mesmo HMAC das outras rotas: horário + corpo (aqui, o JSON exato que será enviado).
const crypto = require('crypto');
const secret = $env.H2D_HMAC_SECRET;
if (!secret) throw new Error('H2D_HMAC_SECRET não configurado');
if (!$env.H2D_API_URL) throw new Error('H2D_API_URL não configurado');

// O evento do H2D está no nó "Montar aviso" (mesmo formato do outbox: type + payload).
const event = $('Montar aviso').first().json.event;
const p = event.payload || {};

const body = JSON.stringify({
  room: 'tecnicos',                         // recepcao | triagem | rag | banco | tecnicos | auditoria
  action: 'aviso_enviado',                  // nome do passo
  summary: `Aviso enviado por e-mail (${event.type})`,   // curto; será limpo pela API
  agent_name: 'n8n',
  ticket_id: p.ticket_id ?? null,           // o payload do outbox traz ticket_id e code
  // O payload não traz o id do solicitante: sem user_id, só técnico e admin veem este evento.
  metadata: { canal: 'email', codigo: p.code ?? null },
});
const ts = String(Math.floor(Date.now() / 1000));
const sig = 'sha256=' + crypto.createHmac('sha256', secret).update(`${ts}.${body}`).digest('hex');
return [{ json: { ts, sig, body, url: `${$env.H2D_API_URL}/api/hooks/n8n/escritorio/events` } }];
```

## Nó 2: HTTP Request, "Enviar evento ao escritório"

| Campo | Valor |
|---|---|
| Method | `POST` |
| URL | `{{ $json.url }}` |
| Send Headers | ligado: `X-H2D-Timestamp` = `{{ $json.ts }}`, `X-H2D-Signature` = `{{ $json.sig }}`, `Content-Type` = `application/json` |
| Send Body | ligado, **Body Content Type: Raw**, Content Type `application/json` |
| Body | `{{ $json.body }}` |
| Options > Timeout | `10000` |
| Settings > On Error | `Continue` (o escritório nunca deve travar o aviso) |

O corpo enviado precisa ser **exatamente** a string assinada no nó 1. Por isso o corpo é montado
uma vez só, como texto, e reaproveitado.

## Respostas

| Status | Significado |
|---|---|
| `201` | Evento gravado. |
| `401` | Assinatura inválida ou horário fora da tolerância de 5 minutos. |
| `404` | Escritório desligado (`ESCRITORIO_VIRTUAL_ENABLED=false`). |
| `422` | Corpo inválido (por exemplo, sala desconhecida). |
| `503` | `N8N_HMAC_SECRET` não configurado na API. |

## Testar à mão

```bash
python - <<'EOF'
import hashlib, hmac, json, time, urllib.request
SECRET = "o-mesmo-segredo-da-api"
body = json.dumps({"room": "rag", "action": "rag_busca", "summary": "teste"}).encode()
ts = str(int(time.time()))
sig = "sha256=" + hmac.new(SECRET.encode(), ts.encode() + b"." + body, hashlib.sha256).hexdigest()
req = urllib.request.Request("http://localhost:8010/api/hooks/n8n/escritorio/events", data=body,
    method="POST", headers={"Content-Type": "application/json",
    "X-H2D-Timestamp": ts, "X-H2D-Signature": sig})
print(urllib.request.urlopen(req).status)
EOF
```
