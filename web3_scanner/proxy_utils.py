from web3 import Web3
from web3_scanner.setting import IMPLEMENTATION_SLOT, BEACON_SLOT, ZEPPELINOS_SLOT,w3
def detect_proxy(address):
    """
    Detect proxy type and fetch implementation address if present.
    Args:
        address (str): Proxy contract address
    Returns:
        tuple(str, str): (proxy_type, implementation_address) or (None, None)
    """
    address = Web3.to_checksum_address(address)
    print(f"[INFO] Checking proxy for contract address: {address}")
    slots = {
        "EIP-1967 Implementation": IMPLEMENTATION_SLOT,
        "EIP-1967 Beacon": BEACON_SLOT,
        "ZeppelinOS Implementation": ZEPPELINOS_SLOT
    }

    # Check proxy types based on storage slots
    for name, slot in slots.items():
        impl_addr = get_implement_address(address, slot)
        if impl_addr:
            print(f"[OK] {name}: {impl_addr}")
            return name, impl_addr

    # Check Minimal Proxy (EIP-1167)
    bytecode = w3.eth.get_code(address).hex()
    if (
        bytecode.startswith("0x363d3d373d3d3d363d73") and
        bytecode.endswith("5af43d82803e903d91602b57fd5bf3")
    ):
        # Extract 20-byte implementation address from the bytecode
        possible_impl = "0x" + bytecode[-46:-6]
        if Web3.is_address(possible_impl):
            possible_impl = Web3.to_checksum_address(possible_impl)
            print(f"[OK] Minimal Proxy (EIP-1167) -> Implementation: {possible_impl}")
            return "Minimal Proxy (EIP-1167)", possible_impl
        else:
            print("[WARN] Minimal Proxy detected but implementation not extracted")
            return "Minimal Proxy (EIP-1167)", None

    print("[ERROR] Proxy not detected")
    return None, None
def get_implement_address(address, slot):
    """
    Retrieve implementation contract address from a proxy contract using a storage slot.
    Args:
        address (str): Proxy contract address (0x...)
        slot (str): Storage slot in hex (e.g., EIP-1967 implementation slot)

    Returns:
        str: Implementation address (0x...) if found, otherwise None.
    """
    raw = w3.eth.get_storage_at(address, slot)  # Get 32-byte data at slot
    if raw and int.from_bytes(raw, 'big') != 0:  # Ensure slot contains data
        # Take last 20 bytes (Ethereum address) and convert to 0x...
        return Web3.to_checksum_address("0x" + raw[-20:].hex())
    return None