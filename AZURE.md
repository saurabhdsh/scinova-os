# SciNova OS — Complete Azure deployment guide

Deploy SciNova on **one Ubuntu VM** with **Docker Compose**, using your **OpenAI** and **Mistral** API keys.

**Recommended VM:** `Standard_DS3_v2` — 4 vCPU, 14 GB RAM (~$70–100/month if always on).

---

## Part A — Before you start (on your Mac)

### A1. What you need

- Azure account: [https://azure.microsoft.com/free](https://azure.microsoft.com/free)
- OpenAI API key: [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys)
- Mistral API key: [https://console.mistral.ai](https://console.mistral.ai)
- GitHub repo URL: `https://github.com/saurabhdsh/scinova-os.git`

### A2. Create an SSH key (Mac Terminal)

Skip if you already have `~/.ssh/id_ed25519.pub` or `id_rsa.pub`.

```bash
ssh-keygen -t ed25519 -C "scinova-azure" -f ~/.ssh/scinova_azure -N ""
cat ~/.ssh/scinova_azure.pub
```

**Copy the entire line** starting with `ssh-ed25519 ...` — you will paste it in the Azure portal.

---

## Part B — Create the VM (Azure Portal)

### B1. Open the VM wizard

1. Go to [https://portal.azure.com](https://portal.azure.com)
2. Top search bar → type **Virtual machines** → open it
3. Click **+ Create** → **Azure virtual machine**

### B2. Basics tab

| Field | What to choose |
|-------|----------------|
| **Subscription** | Your personal subscription |
| **Resource group** | **Create new** → name: `scinova-rg` |
| **Virtual machine name** | `scinova-vm` |
| **Region** | Closest to you (e.g. **Central India**, **East US**, **UK South**) |
| **Availability options** | **No infrastructure redundancy required** |
| **Security type** | **Standard** |
| **Image** | **Ubuntu Server 24.04 LTS - x64 Gen2** |
| **VM architecture** | x64 |
| **Size** | Click **See all sizes** → filter **General purpose** → select **Standard_DS3_v2** (4 vCPU, 14 GiB RAM). Click **Select**. |
| **Username** | `azureuser` (default is fine) |
| **Authentication type** | **SSH public key** |
| **SSH public key source** | **Use existing public key** |
| **Key pair name** | `scinova_azure_key` (any name) |
| **SSH public key** | Paste the output of `cat ~/.ssh/scinova_azure.pub` |
| **Public inbound ports** | **Allow selected ports** |
| **Select inbound ports** | Check **SSH (22)** only |

Click **Next: Disks >**

### B3. Disks tab

| Field | Value |
|-------|--------|
| **OS disk size** | **128 GiB** minimum (256 GiB if you expect many PDFs) |
| **OS disk type** | **Premium SSD (locally redundant)** |

Leave data disks empty. Click **Next: Networking >**

### B4. Networking tab

| Field | Value |
|-------|--------|
| **Virtual network** | Accept default (e.g. `vnet-eastus`) |
| **Subnet** | Default |
| **Public IP** | **(new)** `scinova-vm-ip` — **must be new or existing with static IP** |
| **NIC network security group** | **Basic** |
| **Public inbound ports** | **Allow selected** → **SSH (22)** |

Click **Next: Management** (defaults OK) → **Next: Monitoring** (defaults OK) → **Next: Advanced** (skip) → **Tags** (optional) → **Review + create**.

### B5. Create and wait

1. Click **Create**
2. Wait **2–5 minutes** until **Go to resource**
3. On the VM overview page, copy **Public IP address** (e.g. `20.123.45.67`) — save it; you need it for SSH and `.env`

---

## Part C — Open port 5173 (app UI)

Azure only opens SSH by default. You must allow the web UI port.

### C1. Add inbound rule

1. VM page → left menu **Networking** (under **Settings**)
2. **Network settings** tab → **Create port rule** → **Inbound port rule**
3. Fill in:

| Field | Value |
|-------|--------|
| **Source** | **Any** (or **IP Addresses** + your home IP for tighter security) |
| **Source port ranges** | `*` |
| **Destination** | **Any** |
| **Service** | **Custom** |
| **Destination port ranges** | `5173` |
| **Protocol** | **TCP** |
| **Action** | **Allow** |
| **Priority** | `310` |
| **Name** | `SciNova-UI` |

4. Click **Add**

### C2. (Optional) API port 8000

Only if you want `http://IP:8000/docs` from your browser without going through the UI proxy. Same steps with port **8000**, name `SciNova-API`.

---

## Part D — SSH from your Mac

```bash
ssh -i ~/.ssh/scinova_azure azureuser@<PUBLIC_IP>
```

Replace `<PUBLIC_IP>` with the IP from step B5.

First connect: type `yes` when asked about host authenticity.

You should see a prompt like: `azureuser@scinova-vm:~$`

---

## Part E — Deploy SciNova on the VM

### E1. Clone the repository

```bash
sudo apt-get update -y
sudo apt-get install -y git curl

git clone https://github.com/saurabhdsh/scinova-os.git ~/scinova-os
cd ~/scinova-os
```

If Azure scripts are not on GitHub yet, copy files from your Mac:

```bash
# Run on your Mac (separate terminal):
scp -i ~/.ssh/scinova_azure -r "/Users/saurabhdubey/SciNova OS/scripts" azureuser@<PUBLIC_IP>:~/scinova-os/
scp -i ~/.ssh/scinova_azure "/Users/saurabhdubey/SciNova OS/AZURE.md" azureuser@<PUBLIC_IP>:~/scinova-os/
```

### E2. Run the deploy script

```bash
chmod +x scripts/deploy-azure.sh scripts/preflight-azure.sh
./scripts/deploy-azure.sh
```

This will:

- Install Docker + Docker Compose
- Create `.env` from `.env.example` (if missing)
- Set `CORS_ORIGINS` to your public IP
- Generate a random `SECRET_KEY`
- Run `docker compose build` (10–15 min first time)
- Run `docker compose up -d`

If you see `permission denied` on Docker:

```bash
sudo usermod -aG docker azureuser
exit
```

SSH in again, then:

```bash
cd ~/scinova-os && ./scripts/deploy-azure.sh
```

### E3. Configure API keys

```bash
nano ~/scinova-os/.env
```

Set these (minimum):

```env
OPENAI_API_KEY=sk-your-openai-key-here
OPENAI_BASE_URL=https://api.openai.com/v1
MISTRAL_API_KEY=your-mistral-key-here
MISTRAL_BASE_URL=https://api.mistral.ai/v1

EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
LLM_MODEL=gpt-4o-mini
SLM_MODEL=ministral-8b-latest

CORS_ORIGINS=http://<YOUR_PUBLIC_IP>:5173
ENVIRONMENT=production
```

Save: `Ctrl+O`, Enter, `Ctrl+X`.

Restart services:

```bash
cd ~/scinova-os
docker compose restart backend celery-worker frontend
```

### E4. Run preflight checks

```bash
cd ~/scinova-os
./scripts/preflight-azure.sh
```

Target: **PASS** on RAM, Docker, OpenAI/Mistral reachable, backend `/health`, frontend `:5173`.

---

## Part F — Open SciNova in your browser

On your Mac (or any machine):

```
http://<PUBLIC_IP>:5173
```

| User | Password | Role |
|------|----------|------|
| admin | admin123 | Admin |
| scientist | sci123 | Scientist |
| reviewer | rev123 | Reviewer |

**Before sharing with partners:** create users in **Platform Settings → User Administration** and change default passwords.

---

## Part G — Optional: project workflow

1. Top bar → **+** → create a project (e.g. `JAK1 Pilot`)
2. Select the project in the dropdown
3. **Scientific Data Fabric** → upload PDFs
4. **Ask & Run Agents** → run Target Validation, etc.

All data is scoped to the selected project.

---

## Part H — Billing and cost control

### H1. Azure budget alert

1. Portal → **Cost Management + Billing**
2. **Budgets** → **Add**
3. Scope: your subscription → amount **$50** → alert at 80% and 100%

### H2. OpenAI spend cap

[platform.openai.com](https://platform.openai.com) → **Settings** → **Limits** → set monthly budget.

### H3. Stop VM when not demoing (saves money)

Portal → VM **scinova-vm** → **Stop** (deallocate).

You still pay for disk (~$10–15/month) but not compute. **Start** when you need it again.

---

## Part I — Useful commands (on the VM)

```bash
cd ~/scinova-os

# Status
docker compose ps

# Logs
docker compose logs -f backend
docker compose logs -f frontend

# Restart after .env change
docker compose restart backend celery-worker frontend

# Full rebuild
docker compose down
docker compose build --no-cache
docker compose up -d

# Pull latest code
git pull
docker compose build
docker compose up -d
```

---

## Part J — Troubleshooting

| Problem | Solution |
|---------|----------|
| **SSH connection refused** | VM running? NSG allows port 22? Correct IP? |
| **Browser can't open :5173** | NSG rule for 5173 added? `docker compose ps` shows frontend running? |
| **Blank page / host blocked** | `VITE_ALLOW_ALL_HOSTS=true` in docker-compose; restart frontend |
| **Login works but agents fail** | Check `OPENAI_API_KEY` and `MISTRAL_API_KEY` in `.env`; restart backend |
| **CORS error in browser** | `CORS_ORIGINS=http://<IP>:5173` in `.env`; `docker compose restart backend` |
| **Out of memory** | Resize VM to **DS4_v2** in Portal → VM → **Size** |
| **Build very slow** | Normal on first run; ensure VM has 4+ vCPU |

Check backend health:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:5173/
```

---

## Part K — What runs in Docker

| Container | Port | Purpose |
|-----------|------|---------|
| frontend | 5173 | React UI |
| backend | 8000 | FastAPI API |
| celery-worker | — | Async document ingestion |
| postgres | 5432 | Database |
| neo4j | 7474 / 7687 | Knowledge graph |
| redis | 6379 | Job queue |
| chromadb | 8001 | Vector search |

Data persists in Docker volumes — survives `docker compose restart`.

---

## Quick reference checklist

- [ ] Azure VM **DS3_v2**, Ubuntu 24.04, 128 GB disk
- [ ] NSG: **22** (SSH) + **5173** (UI)
- [ ] SSH works from Mac
- [ ] `git clone` + `./scripts/deploy-azure.sh`
- [ ] `.env` has OpenAI + Mistral keys + `CORS_ORIGINS`
- [ ] `docker compose ps` — 7 services running
- [ ] Browser: `http://<IP>:5173` → login works
- [ ] Upload a test PDF → agent Q&A works
