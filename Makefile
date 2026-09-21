.PHONY: install ingest run test test-all lint format typecheck eval eval-e2e download-nsl train-ml docker-build clean

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

download-nsl:       ## baixa o NSL-KDD (UCI mirror publico) para data/nsl_kdd/
	mkdir -p data/nsl_kdd
	curl -sL -o data/nsl_kdd/KDDTrain+.txt https://raw.githubusercontent.com/defcom17/NSL_KDD/master/KDDTrain%2B.txt
	curl -sL -o data/nsl_kdd/KDDTest+.txt https://raw.githubusercontent.com/defcom17/NSL_KDD/master/KDDTest%2B.txt
	@wc -l data/nsl_kdd/*.txt

train-ml:           ## treina os modelos de ML e gera evals/report_ml.md
	./venv/bin/python scripts/train_ml.py

docker-build:       ## constroi a imagem de producao
	docker build -f docker/Dockerfile -t sentinelasoc .

clean:              ## remove artefatos gerados
	rm -rf .ruff_cache .mypy_cache .pytest_cache dist *.egg-info src/*.egg-info
