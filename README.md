# Automated Smart Contract Penetration Testing using Multi-Agent LLMs
## ⚠️ Disclaimer & Proprietary Notice
> Please note that this repository contains the **Open Core** version of the research framework. Due to the sensitive nature of security research and intellectual property (IP) agreements, certain critical modules and proprietary algorithms have been **selectively redacted or omitted**. 
> 
> The provided code is intended for academic demonstration and reproducibility of the core findings, rather than a full-scale production deployment.
## 1. Introduction

This project presents an **automated penetration testing system for Smart Contracts** powered by **Multi-Agent Large Language Models (LLMs)**.

<figure>
  <img src="https://github.com/user-attachments/assets/d3afc492-42ed-4b78-bd94-eaaec6bfd26c" alt="SMC Architecture">
  <figcaption align="center"><b>Figure 1:</b> SMCVuln Overview.</figcaption>
</figure>

The system enables intelligent agents to:
- Automatically **analyze smart contract targets**
- **Plan penetration testing steps** in multiple phases
- **Execute security analysis tools** in an isolated environment
- **Interpret results and adapt strategies** based on real execution feedback

The primary goal of this project is to **evaluate the reasoning, planning, and adaptive capabilities of LLM-based agents** in the context of **Smart Contract Security**, rather than traditional infrastructure penetration testing.

---

## 2. Origin and Scope

### Original Implementation
- https://github.com/KHenryAegis/VulnBot

### Scope Redefinition
- The original VulnBot focuses on **general-purpose penetration testing (Web2)** 
- This project **reorients the system toward Smart Contract security**, where:
  - Smart contracts are the **primary attack surface**
  - Infrastructure components (Docker, Kali Linux) serve only as **execution environments for security tools**

---

## 3. Key Modifications and Extensions

### 3.1 Code Stabilization
- Fixed syntax and runtime issues in `pentest.py` related to the `click` library to ensure stable execution.

### 3.2 LLM Backend Replacement
- Replaced OpenAI API with **Google Gemini API** to leverage a free-tier LLM.
- Refactored the codebase to ensure compatibility with Gemini models.

### 3.3 Experimental Environment Automation
- Added a `docker-compose.yml` to deploy:
  - Kali Linux (security tool execution)
  - MySQL (state and log storage)
- Ensures **reproducibility of experiments**, which is essential for academic research.

---

## 4. System Architecture

The system consists of the following core components:

- **Planner Agent (LLM-based)**  
  Generates multi-phase penetration testing plans for smart contracts.

- **Executor Agent**  
  Executes static analysis, vulnerability scanning, and exploit attempts within a sandboxed environment.

- **Kali Linux Container**  
  Isolated environment for running security analysis tools.

---
### Project Directory Tree

```text
.
├── actions/                # Workflow orchestration: planning, execution, PoC generation, reporting
├── db/                     # Database models, repositories, and persistence layer
├── experiment/             # LLM-driven experimentation and multi-agent control logic
├── logs/                   # Runtime logs and execution traces
├── prompts/                # Prompt templates for role-specific LLM agents
├── reports/                # Auto-generated penetration testing and remediation reports
├── roles/                  # Definitions of agent roles (collector, exploiter, remediator, etc.)
├── SmartContracts/         # Smart contract samples for testing and security evaluation
├── web3_scanner/           # Web3 scanning and smart contract collection modules
├── bytecode/               # Extracted or compiled smart contract bytecode
├── server/                 # Backend service and API layer
├── utils/                  # Shared utilities and helper functions
```

## 5. Installation and Setup

### 5.1 Environment Preparation

```bash
git clone <repo-url>
cd main
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
2. Service Deployment Using Docker
### 5.2 Create docker-compose.yml with Kali Linux, MySQL
`docker-compose up -d`

### 5.3 Configuration

- Edit the configuration files located in the config/ directory:

  - basic_config.yaml: Kali Linux SSH settings (hostname, port, username, password)

  - db_config.yaml: MySQL database connection

  - model_config.yaml: LLM configuration (API key, model name)
```yaml
api_key: YOUR_API_Key
# aws_region: ''

# LLM provider
llm_model: openai
base_url: 'https://api.openai.com/v1'
llm_model_name: gpt-5-mini-2025-08-07
# Inference parameters
temperature: 1.0
history_len: 5
max_tokens: 10000
timeout: 600
proxies: {}
```
### 5.5 Kali Linux Configuration

- Install and configure the required components inside the Kali Linux container.

- Install SSH service in the Kali Linux container

- Install security tools using the provided installer script

- Inside the Kali Linux container, navigate to the /root directory and run:

`bash installer.sh`
- Inside the Kali Linux container, create "SmartContractTest" directory and init foundry project inside this dic:
`forge init`


*Update the Kali Linux IP address, username, and password in basic_config.yaml accordingly

### 5.6 System Initialization
`python cli.py init`
#### Or alternatively:
`python cli.py scvuln -m 10`
- `-m` : amount of iterations
### 5.7 Run Penetration Testing
- Pentest a Contracts through prompt:
`python pentest.py`
- Or Pentest all Contracts in "SmartContracts" dicrectory:
`./run_all_contracts.sh`
## 6. Demo


https://github.com/user-attachments/assets/3cf889c0-157d-4e3a-bf37-e15a5747d082


## 7. Developers
- Trung, Doan Minh (trungdm@uit.edu.vn)
- Nghi, Tran Gia (https://orcid.org/0009-0005-1630-6551, https://github.com/gianghitran)
- Quang, Nguyen Dinh
- Truong, Tran Van


