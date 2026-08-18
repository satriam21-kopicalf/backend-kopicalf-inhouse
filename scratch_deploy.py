import paramiko
from scp import SCPClient
import sys

host = "187.52.114.14"
user = "root"
passwords = ["Kopicalf2019#", "Klp2024!@"]
local_file = "d:/kopicalf-projection/be-kopicalf-inhouse/app/services/trx_engine.py"
remote_file = "/root/be-kopicalf-inhouse/app/services/trx_engine.py"

def create_ssh_client(server, port, user, password):
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(server, port, user, password)
    return client

ssh = None
for pwd in passwords:
    try:
        ssh = create_ssh_client(host, 22, user, pwd)
        print(f"Connected successfully with a password")
        break
    except paramiko.AuthenticationException:
        print(f"Failed with password {pwd}")
    except Exception as e:
        print(f"Error: {e}")

if not ssh:
    print("Could not connect to the VPS.")
    sys.exit(1)

# SCP the file
try:
    with SCPClient(ssh.get_transport()) as scp:
        scp.put(local_file, remote_file)
        print("File uploaded successfully.")
except Exception as e:
    print(f"SCP Error: {e}")
    sys.exit(1)

# Execute docker restart
commands = [
    "cd /root/be-kopicalf-inhouse && docker compose restart",
    "cd /root/be-kopicalf-inhouse && docker compose ps"
]
for cmd in commands:
    print(f"Executing: {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    exit_status = stdout.channel.recv_exit_status()
    print("Output:")
    print(stdout.read().decode())
    err = stderr.read().decode()
    if err:
        print("Error Output:")
        print(err)

ssh.close()
