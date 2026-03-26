from web3_scanner.flatten_utils import normalize_sources,detect_root_file,topological_order_dfs,flatten_sources, norm_path
from web3_scanner.etherscan_utils import fetch_bytecode, read_addresses, etherscan_get_source
from web3_scanner.proxy_utils import detect_proxy
from web3_scanner.scanner import scan_contracts
from pentest import run_role_session
from db.models.session_model import Session
from utils.log_common import RoleType
from actions.shell_manager import ShellManager 
import sys
import os
import uuid
import time 
from rich.console import Console
from utils.log_common import build_logger

console = Console()
def detectSmartContracts():
    # while True:  # main menu loop
    console.print("\n[bold orange1]Select mode:[/bold orange1]")
    console.print("1. Scan DApp URL to find contracts")
    console.print("2. Input contract addresses manually / from JSON file")
    console.print("0. Exit")
    choice = input("Enter choice: ").strip()

    if choice == "0":
        return  # exit program
    elif choice == "1":
        url = input("Enter DApp URL: ").strip()
        contracts = scan_contracts(url)
        addresses = list(contracts)
        console.print("\n[bold green]Found contracts:[/bold green]")
        for i, addr in enumerate(addresses, 1):
            console.print(f"{i}. {addr}")

        # run_now = input("Run flatten & check proxy for these contracts now? (y/n): ").strip().lower()
        # if run_now != 'y':
        #     continue  # return to main menu
        console.print(f"\n[bold green]Run flatten & check proxy for these contracts now[/bold green]")
    elif choice == "2":
        addresses = read_addresses()
        if not addresses:
            console.print("[bold red]No addresses provided.[/bold red]")
            # continue
            return
    else:
        console.print("[bold red]Invalid choice.[/bold red]")
        # continue
        return
# Clean SmartContracts folder before processing
    smart_contracts_dir = "../SmartContracts"
    if os.path.exists(smart_contracts_dir):
        for file in os.listdir(smart_contracts_dir):
            if file.endswith('.sol'):
                file_path = os.path.join(smart_contracts_dir, file)
                os.remove(file_path)
        console.print(f"[bold yellow]Cleaned existing .sol files from {smart_contracts_dir}[/bold yellow]")
    else:
        os.makedirs(smart_contracts_dir, exist_ok=True)
        console.print(f"[bold yellow]Created directory {smart_contracts_dir}[/bold yellow]")
        
# Process each address: flatten + check proxy
    for address in addresses:
        console.print(f"\n[bold green][i] Processing {address}[/bold green]")
        try:
            # Check proxy
            proxy_type, impl = detect_proxy(address)
            if proxy_type and impl:
                console.print(f"[Proxy] {proxy_type} → {impl}")
                address_to_use = impl
            else:
                console.print("[Proxy] Not a proxy or cannot detect")
                address_to_use = address

            # Try to get verified source
            try:
                row = etherscan_get_source(address_to_use)
                files = normalize_sources(row)
                files = {norm_path(k): v for k, v in files.items()}
                preferred = row.get("ContractName") or None
                root = detect_root_file(files, preferred_contract_name=preferred)
                order, unresolved_imports = topological_order_dfs(files, root)
                flattened = flatten_sources(files, order, unresolved_imports=unresolved_imports)
                out_path = os.path.join("../SmartContracts", f"flatten_{address_to_use}.sol")
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(flattened)
                console.print(f"[OK] Verified contract source written to {out_path}")
            except Exception as e:
                # If the contract is not verified, fall back to bytecode
                console.print(f"[INFO] Contract not verified or error: {e}")
                bytecode = fetch_bytecode(address_to_use)
                if bytecode:
                    os.makedirs("bytecode", exist_ok=True)
                    out_path = os.path.join("bytecode", f"bytecode_{address_to_use}.bin")
                    with open(out_path, "w") as f:
                        f.write(bytecode)
                    print(f"[OK] Bytecode written to {out_path}")
                else:
                    print(f"[ERROR] Cannot fetch bytecode for {address_to_use}")
        except Exception as e:
            print(f"[ERROR] {address}: {e}", file=sys.stderr)
    GetInputTaskstoLLMs()

def GetInputTaskstoLLMs():
    input_tasks = []
    SCNames = []
    
    # Scan SmartContracts folder for all .sol files
    smart_contracts_dir = "SmartContracts"
    if os.path.exists(smart_contracts_dir):
        for file in os.listdir(smart_contracts_dir):
            if file.endswith('.sol'):
                # Remove .sol extension to get contract name
                contract_name = file[:-4]
                SCNames.append(contract_name)
        
        console.print(f"[bold green]Found {len(SCNames)} smart contracts:[/bold green]")
        for name in SCNames:
            console.print(f"  - {name}.sol")
    else:
        console.print(f"[bold red]SmartContracts directory not found![/bold red]")
        return []
    if not SCNames:
        console.print(f"[bold yellow]No .sol files found in {smart_contracts_dir}[/bold yellow]")
        return []
    
    # Note: SSH connection will be established automatically when roles need shell access
    console.print("[bold cyan]SSH connection will be established when needed during analysis[/bold cyan]")
    # Generate tasks for each contract
    for name in SCNames:
        task = f"Perform a comprehensive smart contract security analysis on the contract source code located in the file \"SmartContracts/{name}.sol\" within the current directory."
        input_tasks.append(task)
    
    console.print(f"\n[bold blue]Generated {len(input_tasks)} analysis tasks[/bold blue]")
    
    # Process each task with LLM via pentest.py
    successful_tasks = 0
    failed_tasks = 0
    
    for i, task in enumerate(input_tasks, 1):
        console.print(f"\n[bold cyan]{'='*60}[/bold cyan]")
        console.print(f"[bold cyan]Processing Task {i}/{len(input_tasks)}[/bold cyan]")
        console.print(f"[bold white]Contract: {SCNames[i-1]}.sol[/bold white]")
        console.print(f"[bold cyan]{'='*60}[/bold cyan]")
        
        try:
            # Create a new session with unique ID for proper isolation
            session_id = uuid.uuid4().hex
            
            # Initialize new logger for this task/session
            logger = build_logger()
            logger.info(f"Starting new task analysis for contract: {SCNames[i-1]}.sol")
            logger.info(f"Session ID: {session_id}")
            logger.info(f"Task {i}/{len(input_tasks)}: {task}")
            
            session = Session(
                id=session_id,
                name=f"Smart Contract Analysis - {SCNames[i-1]}",
                current_role_name=RoleType.COLLECTOR.value,
                init_description=task,
                current_planner_id="",
                history_planner_ids=[],
            )
            
            console.print(f"[bold green]Starting analysis for contract {SCNames[i-1]}.sol...[/bold green]")
            console.print(f"[bold blue]Session ID: {session_id}[/bold blue]")
            console.print(f"[bold cyan]Logger initialized: task_{i}_{SCNames[i-1]}_{session_id[:8]}[/bold cyan]")
            
            # Run the role session with proper error handling and cleanup
            session_success = False
            try:
                logger.info("Starting role session execution")
                session_success = run_role_session(console, session, max_interactions=10)
                
                if session_success:
                    logger.info(f"Task {i} completed successfully")
                    console.print(f"[bold green]Task {i} completed successfully![/bold green]")
                    successful_tasks += 1
                else:
                    logger.error(f"Task {i} failed during execution")
                    console.print(f"[bold red]Task {i} failed during execution![/bold red]")
                    failed_tasks += 1
                    
            except Exception as session_error:
                logger.error(f"Session error for task {i}: {session_error}")
                console.print(f"[bold red]Session error for task {i}: {session_error}[/bold red]")
                failed_tasks += 1
                
            # Add a brief pause between sessions to ensure complete cleanup
            import time
            time.sleep(2)
            
            logger.info(f"Session {session_id} completed and cleaned up")
            console.print(f"[bold blue]Session {session_id} completed and cleaned up.[/bold blue]")
                
        except Exception as e:
            if 'logger' in locals():
                logger.error(f"Error processing task {i}: {e}")
            console.print(f"[bold red]Error processing task {i}: {e}[/bold red]")
            failed_tasks += 1
            continue
    
    # Clean up SSH connection
    try:
        ShellManager.get_instance().close()
        console.print("[bold cyan]SSH connection closed.[/bold cyan]")
    except Exception as e:
        console.print(f"[bold yellow]Warning: SSH cleanup error: {e}[/bold yellow]")
    
    # Final summary
    console.print(f"\n[bold cyan]{'='*60}[/bold cyan]")
    console.print(f"[bold green]Analysis Complete![/bold green]")
    console.print(f"[bold white]Total contracts analyzed: {len(input_tasks)}[/bold white]")
    console.print(f"[bold green]Successful: {successful_tasks}[/bold green]")
    console.print(f"[bold red]Failed: {failed_tasks}[/bold red]")
    console.print(f"[bold cyan]{'='*60}[/bold cyan]")
    
    return input_tasks

if __name__ == "__main__":
    while True:
        try:
            # Main menu to choose between detecting new contracts or using existing ones
            console.print("\n[bold cyan]Smart Contract Security Analysis System[/bold cyan]")
            console.print("\n[bold orange1]Choose your option:[/bold orange1]")
            console.print("1. Detect new smart contracts from web3 (DApp URL/addresses)")
            console.print("2. Analyze existing contracts in SmartContracts folder")
            console.print("0. Exit")
            
            choice = input("\nEnter your choice: ").strip()
            
            if choice == "0":
                console.print("[bold yellow]Exiting...[/bold yellow]")
                break
            elif choice == "1":
                console.print("\n[bold green][===Starting web3 contract detection===][/bold green]")
                detectSmartContracts()
                console.print("\n[bold blue][===Proceeding to analyze detected contracts===][/bold blue]")
                continue
            elif choice == "2":
                console.print("\n[bold green][===Analyzing existing contracts in SmartContracts folder===][/bold green]")
                GetInputTaskstoLLMs()
                continue
            else:
                console.print("[bold red]Invalid choice. Exiting...[/bold red]")
                continue

        except Exception as exc:
            console.print(f"\n[bold red][ERROR] {exc}[/bold red]")
            continue