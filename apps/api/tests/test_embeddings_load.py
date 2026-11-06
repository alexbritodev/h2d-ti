import pytest

from h2d.kb.embeddings import LOAD_ATTEMPTS, FastEmbedder


class ModeloFalso:
    def embed(self, texts, batch_size=32):
        return [[1.0, 2.0] for _ in texts]


def test_tenta_de_novo_quando_o_hugging_face_limita_o_download():
    chamadas: list[int] = []
    esperas: list[float] = []

    def loader(nome: str, cache: str):
        chamadas.append(1)
        if len(chamadas) < 3:
            raise OSError("429 Too Many Requests")
        return ModeloFalso()

    embedder = FastEmbedder("/models", loader=loader, sleep=esperas.append)

    assert embedder.embed(["a", "b"]) == [[1.0, 2.0], [1.0, 2.0]]
    assert len(chamadas) == 3
    # A espera cresce a cada tentativa, para dar tempo ao limite de pedidos baixar.
    assert esperas == sorted(esperas) and len(esperas) == 2 and esperas[1] > esperas[0]


def test_desiste_depois_do_limite_com_mensagem_clara_e_nao_fica_em_laco():
    chamadas: list[int] = []

    def loader(nome: str, cache: str):
        chamadas.append(1)
        raise OSError("429 Too Many Requests")

    embedder = FastEmbedder("/models", loader=loader, sleep=lambda _: None)

    with pytest.raises(RuntimeError, match="Não foi possível carregar o modelo"):
        embedder.embed(["a"])

    assert len(chamadas) == LOAD_ATTEMPTS


def test_modelo_carregado_uma_vez_e_reaproveitado():
    chamadas: list[int] = []

    def loader(nome: str, cache: str):
        chamadas.append(1)
        return ModeloFalso()

    embedder = FastEmbedder("/models", loader=loader, sleep=lambda _: None)
    embedder.embed(["a"])
    embedder.embed(["b"])

    assert len(chamadas) == 1
