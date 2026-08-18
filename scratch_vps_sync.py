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
    "cd /root/be-kopicalf-inhouse && git fetch origin main",
    "cd /root/be-kopicalf-inhouse && git reset --hard origin/main",
    "cd /root/be-kopicalf-inhouse && docker compose restart"
]

for cmd in commands:
    print(f"Executing: {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    exit_status = stdout.channel.recv_exit_status()
    print(stdout.read().decode())
    err = stderr.read().decode()
    if err:
        print("ERR:", err)

ssh.close()
print("VPS successfully synced and restarted!")
