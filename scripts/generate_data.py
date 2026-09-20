"""Gera os dados sinteticos do SentinelaSOC (deterministico, seed=42).

Cria 3 tabelas relacionadas:
  data/ativos.csv           - catalogo de ativos (hosts) da Aurora Tecnologia
  data/incidentes.csv       - incidentes de security registrados no SOC
  data/vulnerabilidades.csv - vulnerabilidades detectadas nos ativos

Somente biblioteca padrao (csv, random, datetime) - roda em qualquer Python.
Uso: python scripts/generate_data.py
"""

import csv
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(42)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

HOJE = date(2026, 9, 20)

DEPARTAMENTOS = [
    "Financeiro",
    "Recursos Humanos",
    "Engenharia",
    "Marketing",
    "Juridico",
    "Comercial",
    "Data & Analytics",
    "Infraestrutura",
]

ANALISTAS = [
    "Ana Beatriz",
    "Bruno Carvalho",
    "Camila Souza",
    "Diego Fernandes",
    "Elisa Ramos",
    "Felipe Nogueira",
]

TIPOS_INCIDENTE = [
    ("Phishing", "T1566 - Initial Access"),
    ("Forca Bruta", "T1110 - Credential Access"),
    ("Malware", "T1204 - User Execution"),
    ("DDoS", "T1498 - Impact"),
    ("Exfiltracao de Dados", "T1041 - Exfiltration Over C2"),
    ("Acesso Anomalo", "T1078 - Valid Accounts"),
    ("Vulnerabilidade Explorada", "T1190 - Exploit Public-Facing Application"),
    ("Engenharia Social", "T1598 - Phishing for Information"),
]

DESC_VULNS = [
    ("CVE-2025-2183", "Execucao remota de codigo no servico de autenticacao", 9.8),
    ("CVE-2025-1094", "Injecao de SQL em portal web externo", 8.6),
    ("CVE-2024-4577", "Contorno de validacao em gateway de API", 8.1),
    ("CVE-2025-0282", "Escalada de privilegios local", 7.8),
    ("CVE-2025-22457", "Buffer overflow em cliente VPN", 9.1),
    ("CVE-2024-21762", "Injecao de comando no firewall VPN", 8.2),
    ("CVE-2025-20188", "Divulgacao de informacoes em API interna", 5.3),
    ("CVE-2025-24071", "Vazamento de credenciais em arquivo de log", 6.5),
    ("CVE-2024-38063", "Corrupcao de memoria na pilha de rede", 7.5),
    ("CVE-2025-1974", "Insecure deserialization em microservico", 8.9),
]

SO_PROD = ["Ubuntu Server 22.04 LTS", "Ubuntu Server 24.04 LTS", "RHEL 9.4", "Windows Server 2022"]
SO_DMZ = ["Debian 12", "Alpine 3.20", "Ubuntu Server 22.04 LTS"]


def gerar_ativos():
    ativos = []
    for i in range(1, 41):
        dep = random.choice(DEPARTAMENTOS)
        if i <= 8:  # zona DMZ - expostos
            ambiente = "DMZ"
            hostname = f"dmz-{dep.split()[0].lower()[:4]}-{i:02d}"
            ip = f"200.10.{20 + i}.{10 + i}"
            so = random.choice(SO_DMZ)
            criticidade = random.choice(["Alta", "Alta", "Media"])
            exposto = "Sim"
        else:
            ambiente = random.choice(["Producao", "Producao", "Producao", "Homologacao"])
            hostname = f"{dep.split()[0].lower()[:4]}-{'srv' if i % 3 == 0 else 'ws'}-{i:02d}"
            ip = f"10.{random.randint(1, 4)}.{random.randint(0, 255)}.{random.randint(2, 254)}"
            so = random.choice(SO_PROD)
            criticidade = (
                "Alta"
                if ambiente == "Producao" and i % 4 == 0
                else random.choice(["Media", "Media", "Baixa"])
            )
            exposto = "Nao"
        ativos.append(
            {
                "ativo_id": f"ATV-{i:03d}",
                "hostname": hostname,
                "ip": ip,
                "sistema_operacional": so,
                "ambiente": ambiente,
                "criticidade": criticidade,
                "departamento": dep,
                "responsavel": random.choice(ANALISTAS),
                "exposto_internet": exposto,
            }
        )
    return ativos


def gerar_incidentes(ativos):
    incidentes = []
    n = random.randint(340, 360)
    for i in range(1, n + 1):
        # ativos DMZ/expostos recebem mais incidentes (padrao realista de SOC)
        alvo = random.choice(ativos[:8]) if random.random() < 0.35 else random.choice(ativos)
        tipo, tatica = random.choice(TIPOS_INCIDENTE)

        dias_atras = random.randint(1, 365)
        data_abertura = HOJE - timedelta(days=dias_atras)

        # severidade correlacionada ao tipo e ao ativo
        pesos = {"Critica": 1, "Alta": 3, "Media": 4, "Baixa": 2}
        if tipo in ("Exfiltracao de Dados", "Vulnerabilidade Explorada"):
            pesos = {"Critica": 4, "Alta": 4, "Media": 1, "Baixa": 0}
        if tipo == "DDoS":
            pesos = {"Critica": 1, "Alta": 3, "Media": 3, "Baixa": 1}
        severidade = random.choices(list(pesos), weights=list(pesos.values()))[0]

        # incidentes antigos tendem a estar resolvidos
        if dias_atras > 45:
            status = "Resolvido" if random.random() < 0.92 else "Em atendimento"
        elif dias_atras > 10:
            status = random.choices(["Resolvido", "Em atendimento", "Aberto"], weights=[6, 3, 1])[0]
        else:
            status = random.choices(["Aberto", "Em atendimento", "Resolvido"], weights=[5, 4, 1])[0]

        # rotulo para ML (Etapa 2): falsos positivos mais comuns em severidade baixa
        fp_prob = {"Baixa": 0.55, "Media": 0.30, "Alta": 0.12, "Critica": 0.04}[severidade]
        falso_positivo = "Sim" if random.random() < fp_prob else "Nao"

        horas = ""
        if status == "Resolvido":
            base = {"Critica": 6, "Alta": 14, "Media": 36, "Baixa": 72}[severidade]
            horas = round(random.expovariate(1 / base), 1)

        incidentes.append(
            {
                "incidente_id": f"INC-{data_abertura.year}-{i:04d}",
                "ativo_id": alvo["ativo_id"],
                "data_abertura": data_abertura.isoformat(),
                "tipo": tipo,
                "severidade": severidade,
                "tatica_mitre": tatica,
                "status": status,
                "analista_responsavel": random.choice(ANALISTAS),
                "horas_para_resolver": horas,
                "falso_positivo": falso_positivo,
            }
        )
    incidentes.sort(key=lambda r: r["data_abertura"])
    # renumera apos ordenar para IDs crescentes no tempo
    ano_seq: dict = {}
    for inc in incidentes:
        ano = inc["data_abertura"][:4]
        ano_seq[ano] = ano_seq.get(ano, 0) + 1
        inc["incidente_id"] = f"INC-{ano}-{ano_seq[ano]:04d}"
    return incidentes


def gerar_vulnerabilidades(ativos):
    vulns = []
    n = random.randint(115, 130)
    for i in range(1, n + 1):
        alvo = random.choice(ativos[:8]) if random.random() < 0.30 else random.choice(ativos)
        cve, descricao, cvss_base = random.choice(DESC_VULNS)
        cvss = round(max(1.0, min(9.8, cvss_base + random.uniform(-0.4, 0.4))), 1)
        dias_atras = random.randint(3, 300)
        deteccao = HOJE - timedelta(days=dias_atras)
        if cvss >= 9.0:
            status = random.choices(["Corrigida", "Em correcao", "Aberta"], weights=[4, 4, 2])[0]
        elif cvss >= 7.0:
            status = random.choices(["Corrigida", "Em correcao", "Aberta"], weights=[3, 3, 4])[0]
        else:
            status = random.choices(["Corrigida", "Em correcao", "Aberta"], weights=[3, 2, 5])[0]
        if dias_atras <= 14:
            status = random.choices(["Aberta", "Em correcao"], weights=[3, 2])[0]
        vulns.append(
            {
                "vulnerabilidade_id": f"VULN-{i:03d}",
                "ativo_id": alvo["ativo_id"],
                "cve": cve,
                "descricao": descricao,
                "cvss": cvss,
                "data_deteccao": deteccao.isoformat(),
                "status": status,
                "prazo_sla_dias": 7 if cvss >= 9.0 else (14 if cvss >= 7.0 else 30),
            }
        )
    return vulns


def salvar(nome, linhas):
    caminho = DATA_DIR / nome
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
        w.writeheader()
        w.writerows(linhas)
    print(f"  {caminho}: {len(linhas)} linhas")


if __name__ == "__main__":
    print("Gerando dados sinteticos do SentinelaSOC...")
    ativos = gerar_ativos()
    incidentes = gerar_incidentes(ativos)
    vulns = gerar_vulnerabilidades(ativos)
    salvar("ativos.csv", ativos)
    salvar("incidentes.csv", incidentes)
    salvar("vulnerabilidades.csv", vulns)
    print("Concluido.")
