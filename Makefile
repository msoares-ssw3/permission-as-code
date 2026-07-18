up:      ; docker compose up -d db
migrate: ; python scripts/migrate.py
test:    ; pytest tests/unit tests/integration -q
prop:    ; pytest tests/property -q
golden:  ; pytest tests/golden -q && pytest tests/golden -q
run:     ; uvicorn src.api.main:app --reload
verify-demo: ; python scripts/demo_export.py && python verifier/verify.py /tmp/export.json
