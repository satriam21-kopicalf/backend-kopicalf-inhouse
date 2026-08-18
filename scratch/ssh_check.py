import paramiko
import sys

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
        
    cmd = "cd /root/be-kopicalf-inhouse && docker compose ps -a"
    stdin, stdout, stderr = ssh.exec_command(cmd)
    print(f"--- Output for: {cmd} ---")
    out = stdout.read().decode()
    if out: print(out)
    ssh.close()

if __name__ == '__main__':
    run_ssh('187.52.114.14', 'root', ['Klp2024!@', 'Kopicalf2019#'])
