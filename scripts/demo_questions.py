"""Roda as 5 perguntas canonicas de demonstracao pelo pipeline completo (agente real).

Dupla finalidade: teste end-to-end local (Ollama ou provedor configurado em .env)
e ensaio para o video de demonstracao.

Uso: python scripts/demo_questions.py [n_perguntas]
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sentinelasoc.agent import AgenteSOC
from sentinelasoc.llm import OpenAILLMClient
from sentinelasoc.settings import get_settings

PERGUNTAS = [
    "Qual o prazo para comunicar a ANPD em um incidente com dados pessoais?",
    "Como devo responder a um incidente de phishing?",
    "Qual o SLA de correcao para uma CVE com CVSS 9.5 em um ativo exposto?",
    "Quantos incidentes criticos estao abertos agora e em quais ativos?",
    "Qual a taxa de falsos positivos por tipo de incidente?",
]


def main() -> None:
    s = get_settings()
    print(f"Backend: {s.llm_model} @ {s.openai_base_url or 'https://api.openai.com/v1'}")
    cliente = OpenAILLMClient()
    agente = AgenteSOC(llm=cliente)

    limite = int(sys.argv[1]) if len(sys.argv) > 1 else len(PERGUNTAS)
    for i, pergunta in enumerate(PERGUNTAS[:limite], 1):
        print(f"\n{'=' * 70}\n[{i}/{limite}] PERGUNTA: {pergunta}\n{'-' * 70}")
        inicio = time.perf_counter()
        try:
            resposta = "".join(agente.answer(pergunta))
        except Exception as exc:
            resposta = f"ERRO: {exc}"
        duracao = time.perf_counter() - inicio
        print(resposta[:1200])
        print(
            "\n[trace] "
            + " | ".join(
                f"{t['tipo']}" + (f":{t.get('linhas', '')}linhas" if t["tipo"] == "sql" else "")
                for t in agente.last_trace
            )
        )
        print(f"[tempo total] {duracao:.1f}s")


if __name__ == "__main__":
    main()
