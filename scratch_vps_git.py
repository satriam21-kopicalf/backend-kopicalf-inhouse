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
    sys.exit(1)

stdin, stdout, stderr = ssh.exec_command("cd /root/be-kopicalf-inhouse && git status")
print(stdout.read().decode())
print(stderr.read().decode())

ssh.close()
