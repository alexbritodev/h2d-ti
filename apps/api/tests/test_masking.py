import pytest

from h2d.chat.masking import mask_sensitive

SECRET = "Xk9#mP2vLq8z"


@pytest.mark.parametrize(
    "frase",
    [
        f"minha senha é {SECRET}",
        f"senha: {SECRET}",
        f"SENHA={SECRET}",
        f"password is {SECRET}",
        f'a senha foi "{SECRET}" e não funciona',
    ],
)
def test_senha_digitada_some_do_texto(frase):
    resultado = mask_sensitive(frase)

    assert SECRET not in resultado.text
    assert "[SENHA REMOVIDA]" in resultado.text
    assert resultado.redactions >= 1
    assert "senha" in resultado.kinds


@pytest.mark.parametrize(
    "frase",
    [
        "esqueci a senha da VPN",
        "como troco minha senha do e-mail?",
        "a senha vence a cada 90 dias",
        "preciso de uma nova senha para o sistema",
    ],
)
def test_pergunta_sobre_senha_sem_valor_nao_e_alterada(frase):
    resultado = mask_sensitive(frase)

    assert resultado.text == frase
    assert resultado.redactions == 0


def test_cpf_valido_some_com_ou_sem_pontuacao():
    for cpf in ("529.982.247-25", "52998224725"):
        resultado = mask_sensitive(f"meu cpf é {cpf}, pode confirmar?")

        assert cpf not in resultado.text
        assert "[CPF REMOVIDO]" in resultado.text
        assert "CPF" in resultado.kinds


def test_numero_parecido_com_cpf_mas_invalido_fica():
    texto = "o patrimônio é 123.456.789-00 do notebook"

    assert mask_sensitive(texto).text == texto


def test_cartao_valido_some_e_numero_comum_fica():
    resultado = mask_sensitive("paguei com 4539 1488 0343 6467 ontem")
    comum = mask_sensitive("chamado 1234567890123 aberto")

    assert "4539" not in resultado.text
    assert "[CARTÃO REMOVIDO]" in resultado.text
    assert comum.text == "chamado 1234567890123 aberto"


@pytest.mark.parametrize(
    "token",
    [
        "Bearer abcdefghijklmnopqrstuvwxyz0123",
        "sk-or-v1-abcdefghijklmnopqrstuvwxyz",
        "ghp_abcdefghijklmnopqrstuvwxyz0123",
        "AKIAIOSFODNN7EXAMPLE",
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.abcdefghijk",
        "api_key=abcdef1234567890XYZ",
        "0123456789abcdef0123456789abcdef",
    ],
)
def test_tokens_e_chaves_somem(token):
    resultado = mask_sensitive(f"usei isto: {token} e deu erro")

    assert token not in resultado.text
    assert "[TOKEN REMOVIDO]" in resultado.text
    assert "token" in resultado.kinds


def test_varios_itens_na_mesma_mensagem_contam_todos():
    resultado = mask_sensitive(f"senha: {SECRET} e cpf 52998224725")

    assert resultado.redactions == 2
    assert resultado.kinds == {"senha", "CPF"}
    assert SECRET not in resultado.text
    assert "52998224725" not in resultado.text


def test_texto_normal_passa_sem_alteracao():
    texto = "A VPN cai depois de 12 horas. O erro 809 aparece no Windows 11."

    resultado = mask_sensitive(texto)

    assert resultado.text == texto
    assert resultado.redactions == 0
    assert resultado.kinds == frozenset()
