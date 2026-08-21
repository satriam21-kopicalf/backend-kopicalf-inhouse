import paramiko
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('187.52.114.14', username='root', password='Kopicalf2019#')
stdin, stdout, stderr = client.exec_command('cd /docker/be-kopicalf-inhouse && docker compose logs --tail=100 worker_backfill worker_master api')
print(stdout.read().decode())
client.close()
