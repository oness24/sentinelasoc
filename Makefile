.PHONY: install ingest run test test-all lint format typecheck eval docker-build clean

install:            ## cria venv e instala dependencias de dev
	python3 -m venv venv && ./venv/bin/pip install --upgrade pip
	./venv/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu
	./venv/bin/pip install -e ".[dev]"

ingest:             ## reindexa docs/ no ChromaDB
	./venv/bin/python ingest.py

run:                ## sobe a interface Streamlit
	./venv/bin/streamlit run app.py

test:               ## testes unitarios (sem rede/modelo)
	./venv/bin/python -m pytest -m "not integration and not e2e" -q

test-all:           ## todos os testes (inclui embeddings locais)
	./venv/bin/python -m pytest -q

lint:               ## ruff check
	./venv/bin/ruff check .

format:             ## ruff format
	./venv/bin/ruff format .

typecheck:          ## mypy
	./venv/bin/mypy

eval:               ## benchmark RAG no golden set
	./venv/bin/python evals/evaluate.py

eval-e2e:           ## avaliacao end-to-end com juiz LLM (3 corridas)
	./venv/bin/python evals/evaluate_e2e.py --runs 3

docker-build:       ## constroi a imagem de producao
	docker build -f docker/Dockerfile -t sentinelasoc .

clean:              ## remove artefatos gerados
	rm -rf .ruff_cache .mypy_cache .pytest_cache dist *.egg-info src/*.egg-info
