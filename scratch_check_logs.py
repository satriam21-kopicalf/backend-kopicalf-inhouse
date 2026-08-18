import paramiko
import sys

host = "187.52.114.14"
user = "root"
passwords = ["Kopicalf2019#", "Klp2024!@"]

ssh = paramiko.SSHClient()
ssh.load_system_host_keys()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
connected = False
for pwd in passwords:
    try:
        ssh.connect(host, 22, user, pwd)
        connected = True
        break
    except Exception:
        pass

if not connected:
    print("Failed to connect to VPS")
    sys.exit(1)

commands = [
    "cd /root/be-kopicalf-inhouse && docker compose logs --tail=50 worker_trx_daily",
    "cd /root/be-kopicalf-inhouse && docker compose logs --tail=50 worker_master",
    "cd /root/be-kopicalf-inhouse && docker compose logs --tail=50 worker_backfill",
    "cd /root/be-kopicalf-inhouse && docker compose logs --tail=50 worker_report",
    "cd /root/be-kopicalf-inhouse && docker compose ps"
]

for cmd in commands:
    print(f"\n--- Executing: {cmd} ---")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    print(stdout.read().decode())
    err = stderr.read().decode()
    if err:
        print("ERR:", err)

ssh.close()
