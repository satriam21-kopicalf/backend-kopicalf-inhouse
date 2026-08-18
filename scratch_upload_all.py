import paramiko
from scp import SCPClient
import sys
import os

host = "187.52.114.14"
user = "root"
passwords = ["Kopicalf2019#", "Klp2024!@"]

files_to_upload = [
    ".env.example",
    ".github/workflows/deploy.yml",
    "Dockerfile",
    "app/core/worker.py",
    "app/services/reports.py",
    "app/services/trx_engine.py",
    "docker-compose.yml"
]

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

try:
    with SCPClient(ssh.get_transport()) as scp:
        for file in files_to_upload:
            local_path = os.path.join("d:/kopicalf-projection/be-kopicalf-inhouse", file)
            remote_path = f"/root/be-kopicalf-inhouse/{file}"
            
            # ensure remote directory exists
            remote_dir = os.path.dirname(remote_path)
            ssh.exec_command(f"mkdir -p {remote_dir}")
            
            print(f"Uploading {local_path} to {remote_path}")
            scp.put(local_path, remote_path)
            
    print("All files uploaded successfully.")
except Exception as e:
    print(f"SCP Error: {e}")

# restart containers
print("Restarting containers...")
stdin, stdout, stderr = ssh.exec_command("cd /root/be-kopicalf-inhouse && docker compose restart")
exit_status = stdout.channel.recv_exit_status()
print(stdout.read().decode())
err = stderr.read().decode()
if err:
    print("ERR:", err)

ssh.close()
