# Deploy SciNova OS on the Azure VM

**Preferred path:** start the VM from a Mac with the Azure CLI, then **SSH + `git clone`** on the VM.

This is the Azure counterpart of [deploy_ec2_bedrock.md](./deploy_ec2_bedrock.md). EC2 calls Amazon Bedrock through its instance role. This VM has no AWS role, so agents use **OpenAI** (and Mistral for the small model) from `.env`.

Target host:

| Item | Value |
|------|--------|
| Computer name | `rapid-build-dev-server` |
| Resource group | `RAPID-BUILD-DEV-SERVER_GROUP` |
| Subscription | `az-ai_st-pjpc-01nl166917` |
| Subscription ID | `eb2757c6-7b0f-409c-89a9-3d949470d9d0` |
| Location | East US, availability zone 1 |
| Size | `Standard_D2s_v3` (2 vCPU, 8 GiB) |
| Image | Ubuntu 24.04 LTS, x64, Gen2 |
| Public IP | `20.127.186.132` |
| Private IP | `10.0.0.4` |
| Virtual network | `rapid-build-dev-server-vnet` / `default` |
| NIC | `rapid-build-dev-server999_z1` |
| DNS name | Not configured |
| Git remote | `https://github.com/saurabhdsh/scinova-os.git` |

`Standard_D2s_v3` is the same size class as the EC2 `t3.large`. It is enough for a demo. If Neo4j is killed, resize to `Standard_D4s_v3`.

---

## Quick path: clone, then run one script

On the VM:

```bash
git clone https://github.com/saurabhdsh/scinova-os.git
cd scinova-os
bash scripts/setup_azure.sh
```

That installs Docker if needed, writes an OpenAI `.env` in this clone (`SCINOVA_CLOUD=azure`, Bedrock off), and runs `docker compose up -d --build`.

The public IP is read from the Azure instance metadata service. If that call fails, the script uses `20.127.186.132`.

```bash
PUBLIC_HOST=20.127.186.132 bash scripts/setup_azure.sh
```

Then set the API key in the clone. Do not commit it:

```bash
nano .env
# OPENAI_API_KEY=...
# MISTRAL_API_KEY=...          # only if SLM routing is used
docker compose restart backend celery-worker frontend
bash scripts/preflight-azure.sh
```

---

## Architecture

```
  Your Mac (Azure CLI + SSH key)
           │
           │  1) az vm start
           │  2) ssh azureuser@20.127.186.132
           ▼
  ┌────────────────────────────────────────────┐
  │  rapid-build-dev-server  ·  East US        │
  │  Public IP 20.127.186.132                  │
  │  Ubuntu 24.04  ·  Standard_D2s_v3          │
  │                                            │
  │  git clone scinova-os                      │
  │  docker compose up                         │
  │    frontend :5173                          │
  │    backend  :8000  ──► OpenAI (and Mistral)│
  │    postgres / neo4j / redis / chroma       │
  └────────────────────────────────────────────┘
```

---

## A. On the Mac with Azure CLI

### A1. Sign in and select the subscription

```bash
az login
az account set --subscription "eb2757c6-7b0f-409c-89a9-3d949470d9d0"
az account show --query "{name:name, id:id}" -o table
```

### A2. Start `rapid-build-dev-server`

```bash
az vm start \
  --resource-group "RAPID-BUILD-DEV-SERVER_GROUP" \
  --name "rapid-build-dev-server"

az vm show \
  --resource-group "RAPID-BUILD-DEV-SERVER_GROUP" \
  --name "rapid-build-dev-server" \
  -d \
  --query "{name:name, power:powerState, publicIp:publicIps, privateIp:privateIps, size:hardwareProfile.vmSize}" \
  -o json
```

Expect `VM running` and public IP `20.127.186.132`. That address is static for this NIC today. If Azure ever assigns a new one, set `PUBLIC_HOST` to the new address and re-run the setup script so CORS matches.

### A3. Network security group (SSH + app ports)

The NIC is `rapid-build-dev-server999_z1`. Allow inbound TCP **22**, **5173**, and **8000**. Prefer your current public IP, not `0.0.0.0/0`.

| Port | Use |
|------|-----|
| 22 | SSH from your Mac |
| 5173 | Frontend |
| 8000 | Backend API |

```bash
NSG_ID=$(az network nic show \
  --resource-group "RAPID-BUILD-DEV-SERVER_GROUP" \
  --name "rapid-build-dev-server999_z1" \
  --query "networkSecurityGroup.id" -o tsv)

echo "$NSG_ID"
```

In the portal: VM → Networking → the rule on that NIC → inbound TCP 5173 named `SciNova-UI`, and 8000 named `SciNova-API`.

Do **not** open Postgres (5432), Neo4j (7474/7687), Redis (6379), or Chroma (8001).

### A4. SSH

```bash
ssh azureuser@20.127.186.132
```

Use the admin username chosen when the VM was created if `azureuser` is rejected. There is no DNS name on this VM, so use the public IP.

---

## B. On the VM

```bash
git clone https://github.com/saurabhdsh/scinova-os.git
cd scinova-os
bash scripts/setup_azure.sh
```

Confirm the commit, then the provider line in `.env`:

```bash
git log -1 --oneline
grep -E '^(SCINOVA_CLOUD|DEFAULT_LLM_PROVIDER|BEDROCK_ENABLED)=' .env
```

Expect `SCINOVA_CLOUD=azure`, `DEFAULT_LLM_PROVIDER=openai`, and `BEDROCK_ENABLED=false`.

Open the app at `http://20.127.186.132:5173`.

Demo logins are the same as local: `scientist` / `sci123`. Change them before anyone else uses the VM.

---

## C. Stop the VM when it is idle

Deallocating stops compute charges. The disk and the public IP can still bill.

```bash
az vm deallocate \
  --resource-group "RAPID-BUILD-DEV-SERVER_GROUP" \
  --name "rapid-build-dev-server"
```

Start it again with the `az vm start` command in A2. After a start, SSH in and run `docker compose up -d` inside the clone if the stack does not come back by itself.
