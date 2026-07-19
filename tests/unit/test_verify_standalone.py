"""Sessão 4: verifier/verify.py — stdlib pura, roda sem o resto do repo.

test_cli_* invoca o arquivo como subprocesso (sem importar o pacote) para
provar o requisito de produto: só verify.py + o export.json, zero deps.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from verifier import verify

RAIZ = Path(__file__).resolve().parent.parent.parent
VERIFY_PY = RAIZ / "verifier" / "verify.py"
TENANT = "11111111-1111-1111-1111-111111111111"


def _manifest_valido(n: int = 3) -> dict:
    prev = verify.GENESIS
    eventos = []
    for seq in range(1, n + 1):
        ts = f"2026-01-01T00:00:{seq:02d}.000000+00:00"
        payload = {"n": seq}
        corpo = verify.canonical(
            {
                "tenant_id": TENANT, "seq": seq, "tipo": "t", "origem": "teste",
                "payload": payload, "ts": ts,
            }
        )
        h = verify.hash_evento(prev, corpo)
        eventos.append(
            {
                "seq": seq, "tipo": "t", "origem": "teste", "payload": payload,
                "ts": ts, "prev_hash": prev, "hash": h,
            }
        )
        prev = h
    return {
        "versao": 1, "tenant": TENANT, "gerado_em": "2026-01-01T00:00:10.000000+00:00",
        "seq_de": 1, "seq_ate": n, "algoritmo": verify.ALGORITMO,
        "hash_final": prev, "eventos": eventos,
    }


def test_manifest_integro_verifica_sem_erro() -> None:
    verify.verificar_manifest(_manifest_valido())


def test_1_byte_flipado_aponta_o_seq() -> None:
    manifest = _manifest_valido()
    original = manifest["eventos"][1]["hash"]
    manifest["eventos"][1]["hash"] = ("0" if original[0] != "0" else "1") + original[1:]
    with pytest.raises(verify.CadeiaInvalida, match="seq 2"):
        verify.verificar_manifest(manifest)


def test_cli_maquina_limpa_export_integro(tmp_path: Path) -> None:
    export_path = tmp_path / "export.json"
    export_path.write_text(json.dumps(_manifest_valido()), encoding="utf-8")
    resultado = subprocess.run(
        [sys.executable, str(VERIFY_PY), str(export_path)],
        capture_output=True, text=True,
    )
    assert resultado.returncode == 0
    assert "OK" in resultado.stdout


def test_versao_desconhecida_e_recusada() -> None:
    manifest = _manifest_valido()
    manifest["versao"] = 2
    with pytest.raises(verify.CadeiaInvalida, match="versão"):
        verify.verificar_manifest(manifest)


def _roda_cli(caminho: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VERIFY_PY), str(caminho)],
        capture_output=True, text=True,
    )


def test_cli_arquivo_inexistente_exit_2(tmp_path: Path) -> None:
    resultado = _roda_cli(tmp_path / "nao-existe.json")
    assert resultado.returncode == 2
    assert resultado.stderr.strip() != ""


def test_cli_json_invalido_exit_2(tmp_path: Path) -> None:
    quebrado = tmp_path / "quebrado.json"
    quebrado.write_text("{isso não é json", encoding="utf-8")
    resultado = _roda_cli(quebrado)
    assert resultado.returncode == 2
    assert resultado.stderr.strip() != ""


def test_cli_manifest_sem_campos_exit_2(tmp_path: Path) -> None:
    incompleto = tmp_path / "incompleto.json"
    incompleto.write_text('{"versao": 1}', encoding="utf-8")
    resultado = _roda_cli(incompleto)
    assert resultado.returncode == 2
    assert resultado.stderr.strip() != ""


def test_cli_export_adulterado_falha_apontando_seq(tmp_path: Path) -> None:
    manifest = _manifest_valido()
    manifest["eventos"][0]["payload"] = {"n": 999}
    export_path = tmp_path / "export.json"
    export_path.write_text(json.dumps(manifest), encoding="utf-8")
    resultado = subprocess.run(
        [sys.executable, str(VERIFY_PY), str(export_path)],
        capture_output=True, text=True,
    )
    assert resultado.returncode == 1
    assert "seq 1" in resultado.stdout
