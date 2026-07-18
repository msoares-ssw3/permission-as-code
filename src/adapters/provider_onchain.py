"""Adapter mock determinístico do port ProviderOnchain — Sessão 6.

Zero aleatoriedade: tudo deriva de sha256(seed) (guardrail 1) — mesmo seed,
mesmos bytes, sempre. Sandbox de provider real fica manual, fora da suíte.
"""

from hashlib import sha256

from src.domain.ports import TransferenciaOnchain


class MockProviderOnchain:
    """Gera uma sequência reproduzível de transferências a partir do seed."""

    def __init__(self, seed: str, total: int = 10) -> None:
        self.seed = seed
        self.total = total

    def _hex(self, rotulo: str, i: int) -> str:
        return sha256(f"{self.seed}:{rotulo}:{i}".encode()).hexdigest()

    def _transferencia(self, bloco: int) -> TransferenciaOnchain:
        digest = sha256(f"{self.seed}:valor:{bloco}".encode()).digest()
        return TransferenciaOnchain(
            tx=f"0x{self._hex('tx', bloco)}",
            de=f"0x{self._hex('de', bloco)[:40]}",
            para=f"0x{self._hex('para', bloco)[:40]}",
            valor=int.from_bytes(digest[:4], "big"),
            token="BRLX",
            bloco=bloco,
        )

    def transferencias(self, desde_bloco: int = 0) -> list[TransferenciaOnchain]:
        return [
            self._transferencia(bloco)
            for bloco in range(desde_bloco, self.total)
        ]
