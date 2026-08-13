import paramiko
import time

host = '187.52.114.14'
username = 'root'
password = 'Kopicalf2019#'

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host, username=username, password=password)

print("Connected to VPS")
print("Pulling latest code and restarting docker-compose...")

commands = [
    "cd /root/be-kopicalf-inhouse && git stash && git pull origin main",
    "cd /root/be-kopicalf-inhouse && docker-compose down",
    "cd /root/be-kopicalf-inhouse && docker-compose up -d --build"
]

for cmd in commands:
    print(f"Running: {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd)
    
    # Wait for command to finish
    exit_status = stdout.channel.recv_exit_status()
    print("STDOUT:", stdout.read().decode('utf-8'))
    err = stderr.read().decode('utf-8')
    if err:
        print("STDERR:", err)

print("Deployment complete.")
client.close()
