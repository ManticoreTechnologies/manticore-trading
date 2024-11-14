import os
import sys

def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ["server", "daemon"]:
        print("Usage: python run.py [server|daemon]")
        sys.exit(1)
    
    mode = sys.argv[1]
    if mode == "server":
        os.system("gunicorn -c gunicorn_config.py start_server:server")
    elif mode == "daemon":
        os.system("python start_daemon.py")

if __name__ == "__main__":
    main()

