import paramiko
import os

host = "187.52.114.14"
user = "root"
password = "Kopicalf2019#"

local_path_1 = r"D:\kopicalf-projection\backend-kopicalf-inhouse\app\services\trx_engine.py"
remote_path_1 = "/docker/be-kopicalf-inhouse/app/services/trx_engine.py"

local_path_2 = r"D:\kopicalf-projection\backend-kopicalf-inhouse\reset_db.py"
remote_path_2 = "/docker/be-kopicalf-inhouse/reset_db.py"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    client.connect(host, username=user, password=password, timeout=10)
    print("Successfully connected to VPS")
    
    # SFTP upload
    sftp = client.open_sftp()
    sftp.put(local_path_1, remote_path_1)
    sftp.put(local_path_2, remote_path_2)
    print("Restarting celery workers...")
    # Restart the backend API container
    stdin, stdout, stderr = client.exec_command("cd /docker/be-kopicalf-inhouse && docker compose restart api worker_report worker_trx_daily worker_master worker_backfill celery_beat")
    print(stdout.read().decode())
    print(stderr.read().decode())
    
    client.close()
    print("Services restarted successfully!")
except Exception as e:
    print(f"Error: {e}")
