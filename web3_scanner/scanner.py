import re
import json
import requests
from collections import defaultdict
from web3 import Web3
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

import time
from web3_scanner.setting import HEADERS,w3
def scan_contracts(url: str, output_file="contracts_found.json") -> set:
    """
    Scan a website for Ethereum addresses, verify contracts, and return the set of contract addresses.

    Args:
        url (str): URL of the DApp or website.
        output_file (str): JSON filename to store results.

    Returns:
        set: Collection of smart contract addresses.
    """
    if w3.is_connected():
        print("[INFO] Connected to Infura successfully!")
        print("[INFO] Network ID:", w3.eth.chain_id)
    else:
        print("[ERROR] Failed to connect to Infura RPC. Check API key or network.")
        exit(1)

    found_addresses = set()

    # === STEP 1: Scan static HTML ===
    try:
        html = requests.get(url, headers=HEADERS, timeout=15).text
    except Exception as e:
        print(f"[ERROR] Error fetching HTML: {e}")
        html = ""

    soup = BeautifulSoup(html, "html.parser")

    # Extract addresses in HTML
    html_matches = re.findall(r"0x[a-fA-F0-9]{40}", html)
    for m in html_matches:
        found_addresses.add(m.lower())

    # Extract addresses from scripts
    scripts = [s["src"] for s in soup.find_all("script") if s.get("src")]
    for src in scripts:
        src_url = urljoin(url, src)
        try:
            js_code = requests.get(src_url, headers=HEADERS, timeout=10).text
            js_matches = re.findall(r"0x[a-fA-F0-9]{40}", js_code)
            for m in js_matches:
                found_addresses.add(m.lower())
        except Exception as e:
                print(f"[WARN] Error loading {src_url}: {e}")

    # === STEP 2: Use Playwright to capture dynamic API/data ===
    print("\n[INFO] Launching browser to intercept network...\n")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        def handle_response(response):
            try:
                if "application/json" in response.headers.get("content-type", ""):
                    body = response.text()
                    matches = re.findall(r"0x[a-fA-F0-9]{40}", body)
                    for m in matches:
                        addr = m.lower()
                        print(f"[+] Found address in API response: {addr}")
                        found_addresses.add(addr)
            except:
                pass

        page.on("response", handle_response)
        page.goto(url, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(5000)
        browser.close()

    # === STEP 3: Check contracts ===
    print("\n[INFO] Checking which addresses are smart contracts...\n")
    contract_addresses = set()

    def is_contract(addr):
        try:
            code = w3.eth.get_code(Web3.to_checksum_address(addr))
            time.sleep(0.2)  # delay 0.2s between requests
            if code and code != b'' and code != '0x':
                print(f"[OK] Smart Contract: {addr}")
                return addr
            else:
                print(f"[INFO] EOA or empty: {addr}")
        except Exception as e:
            print(f"[ERROR] Error checking {addr}: {e}")
        return None

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(is_contract, addr) for addr in found_addresses]
        for future in as_completed(futures):
            result = future.result()
            if result:
                contract_addresses.add(result)

    # === STEP 4: Save results and return ===
    with open(output_file, "w") as f:
        json.dump(list(contract_addresses), f, indent=2)

    print("\n[INFO] Final Smart Contract Addresses:")
    for c in contract_addresses:
        print(f" - {c}")

    return contract_addresses
