"""Testes dos prompts: seguranca, formatacao e contexto do dominio."""

import pytest

from sentinelasoc.prompts import FINAL_PROMPT, ROUTER_PROMPT, SQL_PROMPT, SYSTEM_PROMPT


def test_system_prompt_contem_regras_de_seguranca():
    assert "NUNCA revele" in SYSTEM_PROMPT or "nunca revele" in SYSTEM_PROMPT.lower()
    assert "LGPD" in SYSTEM_PROMPT
    assert "SOC" in SYSTEM_PROMPT


def test_router_prompt_define_os_dois_tipos_de_ferramenta():
    assert '"sql"' in ROUTER_PROMPT
    assert '"rag"' in ROUTER_PROMPT


def test_sql_prompt_formata_com_esquema():
    resultado = SQL_PROMPT.format(schema="ESQUEMA_TESTE")
    assert "ESQUEMA_TESTE" in resultado


def test_final_prompt_formata_sem_restos():
    resultado = FINAL_PROMPT.format(pergunta="P?", contexto="C")
    assert "P?" in resultado and "C" in resultado
    assert "{" not in resultado.replace("{{", "").replace("}}", "")


@pytest.mark.parametrize("prompt", [SYSTEM_PROMPT, ROUTER_PROMPT, SQL_PROMPT, FINAL_PROMPT])
def test_prompts_nao_vazios(prompt):
    assert len(prompt) > 200
