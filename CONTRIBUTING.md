# Contribuindo com o SentinelaSOC

Obrigado pelo interesse! Este projeto segue praticas enxutas de engenharia.

## Setup

```bash
make install        # venv + dependencias (torch CPU)
cp .env.example .env   # configure OPENAI_API_KEY
make ingest         # indexa os documentos no ChromaDB
make test           # testes unitarios devem passar antes de qualquer PR
```

## Padroes

- **Estilo**: `ruff format` + `ruff check` (config em `pyproject.toml`). Rode `make format`.
- **Tipos**: `mypy` deve passar sem erros (`make typecheck`).
- **Testes**: unitarios rodam sem rede nem chaves (`make test`). Testes que carregam
  modelos ou chamam LLM usam os marcadores `@pytest.mark.integration` / `@pytest.mark.e2e`.
- **Commits**: Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`).
- **Seguranca**: nunca commite `.env`, chaves ou dados reais. Os dados do repositorio
  sao sinteticos e deterministicos (`scripts/generate_data.py`, seed fixa).

## Checklist de PR

- [ ] `make lint && make typecheck && make test` passam
- [ ] Novas funcionalidades cobertas por testes
- [ ] Sem segredos no diff
- [ ] README/ARCHITECTURE atualizados quando a arquitetura muda
