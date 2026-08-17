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

    # Upload esb.py schema
    print("Uploading app/schemas/esb.py...")
    sftp.put(r"d:\kopicalf-projection\be-kopicalf-inhouse\app\schemas\esb.py", "/root/be-kopicalf-inhouse/app/schemas/esb.py")

    # Upload .env
    print("Uploading .env...")
    sftp.put(r"d:\kopicalf-projection\be-kopicalf-inhouse\.env", "/root/be-kopicalf-inhouse/.env")

    sftp.close()

    print("Restarting docker containers...")
    cmd = "cd /root/be-kopicalf-inhouse && docker compose up -d --build"
    stdin, stdout, stderr = ssh.exec_command(cmd)

    exit_status = stdout.channel.recv_exit_status()
    # Handle stdout/stderr without Unicode issues
    try:
        stdout_data = stdout.read().decode('utf-8', errors='replace')
        stderr_data = stderr.read().decode('utf-8', errors='replace')
        print("Docker compose output received")
        if stdout_data:
            print(f"Stdout: {stdout_data[:500]}")
        if stderr_data:
            print(f"Stderr: {stderr_data[:500]}")
    except Exception as e:
        print(f"Could not read command output: {e}")

    if exit_status == 0:
        print("Deployment successful!")
    else:
        print("Deployment completed with exit status", exit_status)

    ssh.close()

if __name__ == '__main__':
    deploy_to_vps()
