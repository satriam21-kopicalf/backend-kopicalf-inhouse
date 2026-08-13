import paramiko

host = '187.52.114.14'
username = 'root'
password = 'Kopicalf2019#'

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host, username=username, password=password)

print("Connected to VPS")
stdin, stdout, stderr = client.exec_command('cat /root/be-kopicalf-inhouse/.env')
env_content = stdout.read().decode('utf-8')

new_env = []
for line in env_content.splitlines():
    if line.startswith('ESB_CORE_URL='):
        new_env.append('ESB_CORE_URL=https://erp.esb.co.id')
    else:
        new_env.append(line)

new_env_content = '\n'.join(new_env)

# Write back
sftp = client.open_sftp()
with sftp.file('/root/be-kopicalf-inhouse/.env', 'w') as f:
    f.write(new_env_content)
sftp.close()

print("Updated .env file on VPS")

print("Restarting celery...")
client.exec_command("pkill -f 'celery'")
import time; time.sleep(2)
client.exec_command('cd /root/be-kopicalf-inhouse && nohup celery -A app.core.worker worker -B --loglevel=info > celery.log 2>&1 &')

print("Celery restarted.")
client.close()
