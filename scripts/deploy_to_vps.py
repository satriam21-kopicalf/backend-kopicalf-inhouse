import paramiko
import sys

def deploy_to_vps():
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
        
    print("Uploading modified files via SFTP...")
    sftp = ssh.open_sftp()
    
    # Upload main.py
    print("Uploading app/main.py...")
    sftp.put(r"d:\kopicalf-projection\be-kopicalf-inhouse\app\main.py", "/root/be-kopicalf-inhouse/app/main.py")
    
    # Upload tasks.py
    print("Uploading app/services/tasks.py...")
    sftp.put(r"d:\kopicalf-projection\be-kopicalf-inhouse\app\services\tasks.py", "/root/be-kopicalf-inhouse/app/services/tasks.py")
    
    # Upload .env
    print("Uploading .env...")
    sftp.put(r"d:\kopicalf-projection\be-kopicalf-inhouse\.env", "/root/be-kopicalf-inhouse/.env")
    
    sftp.close()
    
    print("Restarting docker containers...")
    cmd = "cd /root/be-kopicalf-inhouse && docker compose up -d --build"
    stdin, stdout, stderr = ssh.exec_command(cmd)
    
    exit_status = stdout.channel.recv_exit_status()
    print("Output:\n", stdout.read().decode('utf-8'))
    print("Error:\n", stderr.read().decode('utf-8'))
    
    if exit_status == 0:
        print("Deployment successful!")
    else:
        print("Deployment failed with exit status", exit_status)
        
    ssh.close()

if __name__ == '__main__':
    deploy_to_vps()
