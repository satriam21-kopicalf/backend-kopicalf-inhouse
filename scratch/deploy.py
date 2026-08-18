import paramiko
import sys
import time

def run_ssh(host, user, passwords):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    connected = False
    for p in passwords:
        try:
            ssh.connect(host, username=user, password=p, timeout=5)
            connected = True
            break
        except Exception as e:
            pass
            
    if not connected:
        print("Failed to connect")
        sys.exit(1)
        
    sftp = ssh.open_sftp()
    print("Uploading fixed python files...")
    
    files_to_upload = [
        (r"d:\kopicalf-projection\be-kopicalf-inhouse\app\core\worker.py", "/root/be-kopicalf-inhouse/app/core/worker.py"),
        (r"d:\kopicalf-projection\be-kopicalf-inhouse\app\services\trx_engine.py", "/root/be-kopicalf-inhouse/app/services/trx_engine.py")
    ]
    
    for local_file, remote_file in files_to_upload:
        sftp.put(local_file, remote_file)
        
    sftp.close()
    
    commands = [
        "cd /root/be-kopicalf-inhouse && docker build -t kopicalf/calf-backend:latest .",
        "cd /root/be-kopicalf-inhouse && docker compose up -d",
        "cd /root/be-kopicalf-inhouse && docker compose ps -a"
    ]
    
    for cmd in commands:
        print(f"--- Running: {cmd} ---")
        stdin, stdout, stderr = ssh.exec_command(cmd)
        
        while True:
            line = stdout.readline()
            if not line:
                break
            print(line, end="")
            
        err = stderr.read().decode()
        if err: print("STDERR:", err)
        
    ssh.close()

if __name__ == '__main__':
    run_ssh('187.52.114.14', 'root', ['Klp2024!@', 'Kopicalf2019#'])
