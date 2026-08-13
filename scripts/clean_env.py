import paramiko

host = '187.52.114.14'
username = 'root'
password = 'Kopicalf2019#'

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host, username=username, password=password)

print("Connected to VPS")
sftp = client.open_sftp()
local_path = '.env'
remote_path = '/root/be-kopicalf-inhouse/.env'

sftp.put(local_path, remote_path)
sftp.close()
print("Uploaded .env to VPS")

print("Restarting celery...")
client.exec_command("pkill -f 'celery'")
import time; time.sleep(2)
client.exec_command('cd /root/be-kopicalf-inhouse && nohup celery -A app.core.worker worker -B --loglevel=info > celery.log 2>&1 &')

print("Celery restarted.")
client.close()
