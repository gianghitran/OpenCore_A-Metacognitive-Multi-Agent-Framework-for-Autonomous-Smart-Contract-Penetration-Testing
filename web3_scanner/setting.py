from web3 import Web3
import re

HEADERS = {"User-Agent": "Mozilla/5.0"}
SEPOLIA_API = "https://api-sepolia.etherscan.io/api"
ETHERSCAN_API_KEY = "{YOUR_API_KEYs}" # set this env var!
INFURA_URL = "https://sepolia.infura.io/v3/{YOUR_URL}"

w3 = Web3(Web3.HTTPProvider(INFURA_URL))
# ---------- Utilities
# Slot chuẩn EIP-1967
IMPLEMENTATION_SLOT = Web3.to_hex( int.from_bytes(Web3.keccak(text="eip1967.proxy.implementation"), byteorder="big") - 1)
BEACON_SLOT = Web3.to_hex(int.from_bytes(Web3.keccak(text="eip1967.proxy.beacon"), byteorder="big") - 1)
ZEPPELINOS_SLOT = Web3.to_hex(int.from_bytes(Web3.keccak(text="org.zeppelinos.proxy.implementation"), byteorder="big"))
IMPORT_RE = re.compile(r'^\s*import\s+(?:(?:"([^"]+)")|(?:\'([^\']+)\')|(?:\{[^}]+\}\s+from\s+"([^"]+)")|(?:\{[^}]+\}\s+from\s+\'([^\']+)\'))\s*;\s*$', re.M)

PRAGMA_SOLIDITY_RE = re.compile(r'^\s*pragma\s+solidity\s+[^;]+;\s*$', re.M)
PRAGMA_OTHER_RE = re.compile(r'^\s*pragma\s+(?!solidity\b)[^;]+;\s*$', re.M)
SPDX_RE = re.compile(r'^\s*//\s*SPDX-License-Identifier:.*$', re.M)
