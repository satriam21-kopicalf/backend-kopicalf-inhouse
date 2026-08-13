import paramiko

host = '187.52.114.14'
username = 'root'
password = 'Kopicalf2019#'

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host, username=username, password=password)

print("Connected to VPS")
sftp = client.open_sftp()
remote_path = '/root/be-kopicalf-inhouse/app/schemas/esb.py'
local_path = 'app/schemas/esb.py'

print(f"Uploading {local_path} to {remote_path}")
sftp.put(local_path, remote_path)
sftp.close()
print("Upload successful!")

# Now start celery in background
print("Starting celery in background...")
# wait a bit for celery to die from previous pkill
import time; time.sleep(2)
client.exec_command('cd /root/be-kopicalf-inhouse && nohup celery -A app.core.worker worker -B --loglevel=info > celery.log 2>&1 &')

client.close()
print("Celery restarted.")
