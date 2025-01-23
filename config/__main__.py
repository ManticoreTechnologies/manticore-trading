"""Command line interface for testing configuration loading"""
from . import settings_conf, evrmore_conf
import json
from pathlib import Path

def main():
    """Display loaded configuration"""
    print("\nSettings Configuration:")
    print("-" * 50)
    for key, value in settings_conf.items():
        print(f"{key}: {value}")
        
    print("\nEvrmore Configuration:")
    print("-" * 50)
    for key, value in evrmore_conf.items():
        print(f"{key}: {value}")
        
    # Save example configuration files
    examples_dir = Path("examples")
    examples_dir.mkdir(exist_ok=True)
    
    with open(examples_dir / "settings.conf.example", "w") as f:
        f.write("""[DEFAULT]
# Path to Evrmore configuration directory
evrmore_root = /home/user/.evrmore/
""")
        
    with open(examples_dir / "evrmore.conf.example", "w") as f:
        f.write("""# Evrmore configuration file
mainnet=1
miningaddress=ESDwJs2FX5zYoVnLQ7YuLZhmnsAcpKqMiq
server=1
whitelist=0.0.0.0/0
txindex=1
addressindex=1
assetindex=1
timestampindex=1
spentindex=1
zmqpubhashtxhwm=10000
zmqpubhashblockhwm=10000
zmqpubrawblockhwm=10000
zmqpubrawtxhwm=10000
zmqpubsequencehwm=10000
zmqpubhashtx=tcp://127.0.0.1:2936
zmqpubrawblock=tcp://127.0.0.1:2935
zmqpubsequence=tcp://127.0.0.1:2934
zmqpubrawtx=tcp://127.0.0.1:29332
zmqpubhashblock=tcp://127.0.0.1:29333
port=8820
rpcbind=0.0.0.0
rpcport=8819
rpcallowip=0.0.0.0/0
rpcuser=user
rpcpassword=password
uacomment=my_evr_node
mempoolexpiry=72
rpcworkqueue=1100
maxmempool=2000
dbcache=1000
maxtxfee=1.0
""")

if __name__ == "__main__":
    main()
