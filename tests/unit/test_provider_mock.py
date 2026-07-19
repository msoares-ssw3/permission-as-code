"""Sessão 6: o mock do provider é determinístico — mesmo seed, mesmos bytes."""

from src.adapters.provider_onchain import MockProviderOnchain


def test_mesmo_seed_mesma_sequencia() -> None:
    a = MockProviderOnchain("demo").transferencias()
    b = MockProviderOnchain("demo").transferencias()
    assert a == b
    assert len(a) == 10
    assert all(isinstance(t.valor, int) for t in a)


def test_seed_diferente_sequencia_diferente_e_desde_bloco() -> None:
    a = MockProviderOnchain("demo").transferencias()
    c = MockProviderOnchain("outro").transferencias()
    assert a != c
    assert MockProviderOnchain("demo").transferencias(desde_bloco=7) == a[7:]
