#!/usr/bin/env python3
"""
Deploy automático do UEFN AI Map Generator num servidor Hetzner novo.

Uso:
    pip install paramiko requests
    python deploy_hetzner.py

Variáveis necessárias (edita abaixo ou passa como variáveis de ambiente):
    HETZNER_TOKEN    — token da API Hetzner Cloud
    ANTHROPIC_API_KEY — API key da Anthropic para o Claude
"""

import os
import sys
import time
import json
import textwrap
import requests
import paramiko
from pathlib import Path

# ============================================================
# CONFIGURAÇÃO — edita estas variáveis ou usa variáveis de ambiente
# ============================================================
HETZNER_TOKEN     = os.getenv("HETZNER_TOKEN",     "9Oj7wxhUJhU6K2iSkNmbe6lVOlRQwSLsbjcysicpQqSLdCK5qb7sYCYJPKnY3goJ")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")   # <-- preenche aqui

SERVER_NAME  = "uefn-map-generator"
SERVER_TYPE  = "cx22"          # 2 vCPU, 4GB RAM (~€4/mês)
IMAGE        = "ubuntu-22.04"
LOCATION     = "nbg1"          # Nuremberga, Europa
APP_PORT     = 8501
DEPLOY_DIR   = "/opt/uefn_generator"
# ============================================================

HEADERS = {
    "Authorization": f"Bearer {HETZNER_TOKEN}",
    "Content-Type": "application/json",
}

# Ficheiros da app a copiar para o servidor
APP_DIR = Path(__file__).parent
APP_FILES = [
    "app.py",
    "system_prompt.py",
    "claude_client.py",
    "styles.py",
    "requirements.txt",
]


def log(msg: str, icon: str = "→"):
    print(f"  {icon}  {msg}")


def create_server() -> tuple[str, str, int]:
    """Cria servidor Hetzner. Devolve (ip, root_password, server_id)."""
    log("A criar servidor Hetzner...", "🚀")

    resp = requests.post(
        "https://api.hetzner.cloud/v1/servers",
        headers=HEADERS,
        json={
            "name": SERVER_NAME,
            "server_type": SERVER_TYPE,
            "image": IMAGE,
            "location": LOCATION,
            "start_after_create": True,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    server    = data["server"]
    root_pw   = data.get("root_password", "")
    ip        = server["public_net"]["ipv4"]["ip"]
    server_id = server["id"]

    log(f"Servidor criado! ID: {server_id}", "✅")
    log(f"IP: {ip}")
    log(f"Password root: {root_pw}")
    log("A aguardar que o servidor fique ativo...", "⏳")

    # Aguardar status "running"
    for attempt in range(30):
        time.sleep(5)
        r = requests.get(
            f"https://api.hetzner.cloud/v1/servers/{server_id}",
            headers=HEADERS, timeout=10,
        )
        status = r.json()["server"]["status"]
        if status == "running":
            log(f"Servidor ativo após {(attempt+1)*5}s", "✅")
            break
        log(f"Status: {status} (tentativa {attempt+1}/30)...", "⏳")
    else:
        raise TimeoutError("Servidor não ficou ativo em 150 segundos")

    # Aguardar SSH estar pronto
    log("A aguardar que o SSH fique disponível...", "⏳")
    time.sleep(20)

    return ip, root_pw, server_id


def run_ssh(client: paramiko.SSHClient, cmd: str, check: bool = True) -> str:
    """Executa um comando SSH e devolve o output."""
    stdin, stdout, stderr = client.exec_command(cmd, timeout=120)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()

    if check and exit_code != 0:
        raise RuntimeError(f"Comando falhou (exit {exit_code}):\n{cmd}\nERRO: {err}")
    return out


def upload_files(sftp: paramiko.SFTPClient, remote_dir: str):
    """Copia ficheiros da app para o servidor."""
    for filename in APP_FILES:
        local_path = APP_DIR / filename
        remote_path = f"{remote_dir}/{filename}"
        if local_path.exists():
            sftp.put(str(local_path), remote_path)
            log(f"Uploaded: {filename}", "📤")
        else:
            log(f"Ficheiro não encontrado (a ignorar): {filename}", "⚠️")


def deploy(ip: str, root_pw: str):
    """Faz deploy completo da app no servidor via SSH."""

    if not ANTHROPIC_API_KEY:
        print("\n⚠️  ANTHROPIC_API_KEY não definida!")
        ANTHROPIC_API_KEY_val = input("   Insere a tua ANTHROPIC_API_KEY: ").strip()
    else:
        ANTHROPIC_API_KEY_val = ANTHROPIC_API_KEY

    log(f"A ligar ao servidor {ip}...", "🔗")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # Tentar ligar (com retry pois o SSH pode ainda não estar pronto)
    for attempt in range(10):
        try:
            ssh.connect(ip, username="root", password=root_pw, timeout=15)
            log("SSH ligado!", "✅")
            break
        except Exception as e:
            if attempt < 9:
                log(f"SSH ainda não disponível, a aguardar... ({attempt+1}/10)", "⏳")
                time.sleep(10)
            else:
                raise RuntimeError(f"Não foi possível ligar via SSH: {e}")

    try:
        # 1. Atualizar sistema
        log("A atualizar o sistema...", "📦")
        run_ssh(ssh, "DEBIAN_FRONTEND=noninteractive apt-get update -qq && "
                     "apt-get upgrade -y -qq")

        # 2. Instalar dependências
        log("A instalar Python 3.11 e dependências...", "📦")
        run_ssh(ssh, "DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "
                     "python3.11 python3-pip python3-venv git ufw")

        # 3. Criar directoria da app
        log(f"A criar directoria {DEPLOY_DIR}...", "📁")
        run_ssh(ssh, f"mkdir -p {DEPLOY_DIR}")

        # 4. Copiar ficheiros via SFTP
        log("A copiar ficheiros da app...", "📤")
        sftp = ssh.open_sftp()
        upload_files(sftp, DEPLOY_DIR)
        sftp.close()

        # 5. Criar venv e instalar requirements
        log("A instalar dependências Python...", "🐍")
        run_ssh(ssh, f"cd {DEPLOY_DIR} && python3 -m venv venv && "
                     f"venv/bin/pip install --quiet -r requirements.txt")

        # 6. Criar ficheiro .env
        log("A configurar variáveis de ambiente...", "🔑")
        env_content = f"ANTHROPIC_API_KEY={ANTHROPIC_API_KEY_val}\n"
        run_ssh(ssh, f"echo '{env_content}' > {DEPLOY_DIR}/.env && "
                     f"chmod 600 {DEPLOY_DIR}/.env")

        # 7. Configurar firewall
        log("A configurar firewall...", "🔒")
        run_ssh(ssh, f"ufw allow 22/tcp && ufw allow {APP_PORT}/tcp && "
                     "ufw --force enable", check=False)

        # 8. Criar serviço systemd
        log("A configurar serviço systemd...", "⚙️")
        service_content = textwrap.dedent(f"""
            [Unit]
            Description=UEFN AI Map Generator
            After=network.target

            [Service]
            WorkingDirectory={DEPLOY_DIR}
            EnvironmentFile={DEPLOY_DIR}/.env
            ExecStart={DEPLOY_DIR}/venv/bin/streamlit run app.py \\
                --server.port {APP_PORT} \\
                --server.address 0.0.0.0 \\
                --server.headless true \\
                --browser.gatherUsageStats false
            Restart=always
            RestartSec=5
            User=root

            [Install]
            WantedBy=multi-user.target
        """).strip()

        # Escrever ficheiro de serviço
        run_ssh(ssh, f"cat > /etc/systemd/system/uefn-generator.service << 'SERVICEEOF'\n"
                     f"{service_content}\nSERVICEEOF")

        # 9. Ativar e iniciar serviço
        log("A iniciar serviço...", "🚀")
        run_ssh(ssh, "systemctl daemon-reload && "
                     "systemctl enable uefn-generator && "
                     "systemctl start uefn-generator")

        # 10. Verificar status
        time.sleep(5)
        status = run_ssh(ssh, "systemctl is-active uefn-generator", check=False)
        if status == "active":
            log("Serviço ativo!", "✅")
        else:
            log(f"Status do serviço: {status}", "⚠️")
            logs = run_ssh(ssh, "journalctl -u uefn-generator -n 20 --no-pager", check=False)
            log(f"Logs:\n{logs}", "📋")

    finally:
        ssh.close()

    print(f"\n{'='*60}")
    print(f"  ✅  Deploy concluído!")
    print(f"{'='*60}")
    print(f"  🌐  URL: http://{ip}:{APP_PORT}")
    print(f"  🖥️  Servidor: {SERVER_TYPE} Ubuntu 22.04 em {LOCATION}")
    print(f"  📝  Gestão: systemctl status uefn-generator")
    print(f"{'='*60}\n")


def main():
    print("\n" + "="*60)
    print("  🗺️  UEFN AI Map Generator — Deploy Hetzner")
    print("="*60 + "\n")

    if not HETZNER_TOKEN:
        print("❌ HETZNER_TOKEN não definido!")
        sys.exit(1)

    try:
        ip, root_pw, server_id = create_server()
        deploy(ip, root_pw)
    except KeyboardInterrupt:
        print("\n\nDeploy cancelado pelo utilizador.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erro durante o deploy: {e}")
        raise


if __name__ == "__main__":
    main()
