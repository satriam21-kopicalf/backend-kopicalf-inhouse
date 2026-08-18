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
        
    sftp = ssh.open_sftp()
    try:
        # copy the file from container to host first
        ssh.exec_command("docker cp be-kopicalf-inhouse-celery_beat-1:/app/app/services/reports.py /root/reports.py")
        import time
        time.sleep(2)
        sftp.get("/root/reports.py", "scratch/reports_vps.py")
        print("Successfully got reports.py from VPS")
    except Exception as e:
        print("Error:", e)
        
    sftp.close()
    ssh.close()

if __name__ == '__main__':
    run_ssh('187.52.114.14', 'root', ['Klp2024!@', 'Kopicalf2019#'])
