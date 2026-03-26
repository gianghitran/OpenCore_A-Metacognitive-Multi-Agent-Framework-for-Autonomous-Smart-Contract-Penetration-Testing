from web3_scanner.setting import HEADERS, SEPOLIA_API, ETHERSCAN_API_KEY
import requests
from web3 import Web3
import json
from pathlib import Path

def fetch_bytecode(address):
    """
    Lấy bytecode của một địa chỉ trên mạng Sepolia thông qua API của Etherscan.
    Args:
        address (str): Địa chỉ Ethereum (0x...) cần lấy bytecode.
    Returns:
        str | None:
            - Mã bytecode ở dạng hex string (ví dụ: '0x6080604052...') nếu tồn tại.
            - None nếu địa chỉ không chứa smart contract hoặc không lấy được dữ liệu.
    Cách hoạt động:
        - Gọi API Etherscan với module=proxy và action=eth_getCode.
        - API này tương tự RPC method `eth_getCode` nhưng được truy vấn qua Etherscan.
        - Nếu trả về `"result" == "0x"` → nghĩa là địa chỉ không chứa smart contract (EOA hoặc trống).
        - Ngược lại → trả về mã bytecode để phục vụ phân tích (Slither, Mythril...).
    Lưu ý:
        - Hàm này dùng SEPOLIA_API thay vì INFURA_URL vì lấy qua Etherscan API.
        - Bạn cần ETHERSCAN_API_KEY hợp lệ để truy vấn.
        - Nếu muốn lấy bytecode trực tiếp qua node (không qua Etherscan) thì dùng:
            w3.eth.get_code(address).hex()
    """
    url = (
        f"{SEPOLIA_API}"
        f"?module=proxy&action=eth_getCode"
        f"&address={address}&apikey={ETHERSCAN_API_KEY}"
    )
    res = requests.get(url)
    data = res.json()
    # Nếu kết quả hợp lệ và không rỗng → trả về bytecode hex
    if "result" in data and data["result"] != "0x":
        return data["result"]
    # Không có contract tại địa chỉ
    return None


def read_addresses() -> list[str]:
    choice = input("Enter '1' to input single address or '2' to load from file: ").strip()
    if choice == "1":
        addr = input("Enter contract address (0x...): ").strip()
        if Web3.is_address(addr):
            return [Web3.to_checksum_address(addr)]
        print("Invalid Ethereum address.")
        return []
    elif choice == "2":
        file_path = input("Enter JSON file path with addresses: ").strip()
        if not Path(file_path).exists():
            print(f"File {file_path} not found!")
            return []
        with open(file_path, "r") as f:
            data = json.load(f)
        addresses = []
        for a in data:
            if Web3.is_address(a):
                addresses.append(Web3.to_checksum_address(a))
        return addresses
    else:
        print("Invalid choice.")
        return []



def etherscan_get_source(address: str) -> dict:
    """Return Etherscan result dict (first row). Raises on error."""
    if not ETHERSCAN_API_KEY:
        raise RuntimeError("Please set ETHERSCAN_API_KEY environment variable.")
    params = {
        "module": "contract",
        "action": "getsourcecode",
        "address": address,
        "apikey": ETHERSCAN_API_KEY,
    }
    resp = requests.get(SEPOLIA_API, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "1" or not data.get("result"):
        raise RuntimeError(f"Etherscan error: {data}")
    row = data["result"][0]
    if not row.get("SourceCode"):
        raise RuntimeError("Contract is not verified or source is empty.")
    return row