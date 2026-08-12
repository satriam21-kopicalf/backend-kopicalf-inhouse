import paramiko
import sys

def check_logs():
    host = '187.52.114.14'
    user = 'root'
    password = 'Kopicalf2019#'
    
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    print(f"Connecting to {host}...")
    try:
        ssh.connect(host, username=user, password=password, timeout=10)
    except Exception as e:
        print(f"Failed to connect: {e}")
        sys.exit(1)
        
    print("Checking Celery logs...")
    cmd = "docker logs --tail 100 be-kopicalf-inhouse-celery_worker-1"
    stdin, stdout, stderr = ssh.exec_command(cmd)
    print("Celery Worker Logs:\n", stdout.read().decode('utf-8'))
    print("Celery Worker Err:\n", stderr.read().decode('utf-8'))
    
    cmd = "docker logs --tail 50 be-kopicalf-inhouse-api-1"
    stdin, stdout, stderr = ssh.exec_command(cmd)
    print("API Logs:\n", stdout.read().decode('utf-8'))
    
    ssh.close()

if __name__ == '__main__':
    check_logs()
