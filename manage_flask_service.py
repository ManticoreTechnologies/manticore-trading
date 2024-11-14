import os
import subprocess
from helper import settings

SERVICE_NAME = "manticore-trading"
SERVICE_FILE = f"/etc/systemd/system/{SERVICE_NAME}.service"

SERVICE_CONTENT = f"""[Unit]
Description=Manticore Trading Flask Service
After=network.target

[Service]
User=root
Group=root
WorkingDirectory={os.getcwd()}
ExecStart=python3 run.py server
Restart=always

[Install]
WantedBy=multi-user.target
"""

def install_service():
    # Write the service file
    with open(SERVICE_FILE, "w") as file:
        file.write(SERVICE_CONTENT)

    # Set permissions for the service file
    os.chmod(SERVICE_FILE, 0o644)

    # Reload systemd to recognize the new service
    subprocess.run(["systemctl", "daemon-reload"], check=True)

    # Enable the service to start on boot
    subprocess.run(["systemctl", "enable", SERVICE_NAME], check=True)

    # Start the service immediately
    subprocess.run(["systemctl", "start", SERVICE_NAME], check=True)

    print(f"Service '{SERVICE_NAME}' installed and started successfully.")

def uninstall_service():
    # Stop the service if it's running
    subprocess.run(["systemctl", "stop", SERVICE_NAME], check=True)

    # Disable the service to prevent it from starting on boot
    subprocess.run(["systemctl", "disable", SERVICE_NAME], check=True)

    # Remove the service file
    if os.path.exists(SERVICE_FILE):
        os.remove(SERVICE_FILE)

    # Reload systemd to apply the changes
    subprocess.run(["systemctl", "daemon-reload"], check=True)

    print(f"Service '{SERVICE_NAME}' uninstalled successfully.")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Install or uninstall the Manticore Crypto Faucet service.")
    parser.add_argument("action", choices=["install", "uninstall"], help="Action to perform: 'install' or 'uninstall' the service.")

    args = parser.parse_args()

    if args.action == "install":
        install_service()
    elif args.action == "uninstall":
        uninstall_service()
