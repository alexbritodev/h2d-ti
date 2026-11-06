"""Esconde dado sensível antes de qualquer gravação, log ou envio ao modelo.

Roda sobre o texto do usuário assim que ele chega: o que sai daqui é o único texto que o resto do
sistema enxerga. Senha, CPF, cartão e token nunca chegam ao banco nem ao provedor de LLM.
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Masked:
    text: str
    redactions: int
    kinds: frozenset[str]


def _valid_cpf(digits: str) -> bool:
    if len(digits) != 11 or len(set(digits)) == 1:
        return False
    for size in (9, 10):
        total = sum(int(d) * w for d, w in zip(digits[:size], range(size + 1, 1, -1), strict=True))
        if (total * 10 % 11) % 10 != int(digits[size]):
            return False
    return True


def _luhn(digits: str) -> bool:
    total = 0
    for index, char in enumerate(reversed(digits)):
        value = int(char)
        if index % 2 == 1:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


_CPF = re.compile(r"(?<!\d)(\d{3}\.?\d{3}\.?\d{3}-?\d{2})(?!\d)")
_CARD = re.compile(r"(?<!\d)(\d(?:[ -]?\d){12,18})(?!\d)")

# "senha: abc", "minha senha é abc", "password=abc". Sem separador ("senha da VPN") não mascara.
_PASSWORD = re.compile(
    r"(?i)\b(senha|password|passwd|pwd|pass)\b(\s*(?:[:=]|é|eh|is|foi|sera|será)\s*)([\"']?)([^\s\"']{3,})\3"
)

_TOKENS = [
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-]{16,}"),
    re.compile(r"\beyJ[A-Za-z0-9_\-]{5,}\.[A-Za-z0-9_\-]{5,}\.[A-Za-z0-9_\-]{5,}"),
    re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"\b(?:ghp|gho|ghs|github_pat)_[A-Za-z0-9_]{16,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}"),
    re.compile(r"(?i)\b(?:api[_-]?key|token|secret|chave)\b\s*[:=]\s*[\"']?[A-Za-z0-9._\-/+]{12,}"),
    re.compile(r"\b[A-Fa-f0-9]{32,}\b"),
]


def mask_sensitive(text: str) -> Masked:
    kinds: set[str] = set()
    count = 0

    def sub_password(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        kinds.add("senha")
        return f"{match.group(1)}{match.group(2)}[SENHA REMOVIDA]"

    text = _PASSWORD.sub(sub_password, text)

    for pattern in _TOKENS:

        def sub_token(_: re.Match[str]) -> str:
            nonlocal count
            count += 1
            kinds.add("token")
            return "[TOKEN REMOVIDO]"

        text = pattern.sub(sub_token, text)

    def sub_card(match: re.Match[str]) -> str:
        nonlocal count
        digits = re.sub(r"\D", "", match.group(1))
        if 13 <= len(digits) <= 19 and _luhn(digits):
            count += 1
            kinds.add("cartão")
            return "[CARTÃO REMOVIDO]"
        return match.group(0)

    text = _CARD.sub(sub_card, text)

    def sub_cpf(match: re.Match[str]) -> str:
        nonlocal count
        if _valid_cpf(re.sub(r"\D", "", match.group(1))):
            count += 1
            kinds.add("CPF")
            return "[CPF REMOVIDO]"
        return match.group(0)

    text = _CPF.sub(sub_cpf, text)
    return Masked(text=text, redactions=count, kinds=frozenset(kinds))
