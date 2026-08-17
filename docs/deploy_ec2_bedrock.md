# Deploy SciNova OS on AWS EC2 + Amazon Bedrock

**Preferred path:** control AWS from a **Mac with AWS CLI**, then **SSH + `git clone`** on the EC2.

Target host:

| Item | Value |
|------|--------|
| Instance name | `weave-server` |
| Instance ID | `i-0dea21dad454d0b31` |
| Type | `t3.large` (2 vCPU, 8 GiB) |
| Region | `us-east-1` |
| Elastic IP | `52.0.130.62` |
| IAM role | `WeaveEC2BedrockRole` |
| Git remote | `https://github.com/saurabhdsh/scinova-os.git` |

**Note:** Molecular Discovery Studio (Char-RNN + RDKit) runs on **EC2 CPU**. Bedrock is for SciNova agents / chat / ontology / embeddings.

---

## Quick path: one-shot script on EC2

After SSH (and after this repo is pushed to GitHub):

```bash
# Option A — bootstrap without a prior clone (public repo)
curl -fsSL https://raw.githubusercontent.com/saurabhdsh/scinova-os/main/scripts/setup_ec2.sh | bash

# Option B — private repo (PAT in env, not in shell history if possible)
export GITHUB_TOKEN=ghp_xxx
curl -fsSL https://raw.githubusercontent.com/saurabhdsh/scinova-os/main/scripts/setup_ec2.sh | bash

# Option C — already cloned
cd ~/SciNova-OS && bash scripts/setup_ec2.sh
```

The script installs Docker/AWS CLI (if needed), clones/pulls `main`, writes a Bedrock `.env` (IAM role, no access keys), optionally runs `scripts/test-bedrock.sh`, then `docker compose up -d --build`.

Override defaults:

```bash
PUBLIC_HOST=52.0.130.62 \
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0 \
bash scripts/setup_ec2.sh
```

---


`git clone` on EC2 only gets what is **pushed to GitHub**.

1. Commit and push Molecular Discovery Studio + Bedrock-ready code to `main` (or a deploy branch).
2. Confirm on GitHub that the latest commit includes what you want to run.
3. On the **other Mac** (AWS CLI): you only need AWS credentials, the SSH key (`.pem`), and optionally a GitHub PAT if the repo is private.

If you skip the push, EC2 will clone an older tree without MDS / latest chem services.

---

## Architecture on EC2

```
  Your Mac (AWS CLI + SSH key)
           │
           │  1) aws ec2 start-instances
           │  2) ssh …@52.0.130.62
           ▼
  ┌────────────────────────────────────┐
  │  EC2 weave-server  ·  us-east-1    │
  │  EIP 52.0.130.62                   │
  │  IAM WeaveEC2BedrockRole           │
  │                                    │
  │  git clone scinova-os              │
  │  docker compose up                 │
  │    frontend :5173                  │
  │    backend  :8000  ──► Bedrock     │
  │    postgres / neo4j / redis / …    │
  └────────────────────────────────────┘
```

---

## A. On the Mac with AWS CLI

### A1. Configure / check AWS CLI

```bash
aws configure list
aws sts get-caller-identity
export AWS_REGION=us-east-1
export AWS_DEFAULT_REGION=us-east-1
```

You should see your account and a principal that can start EC2.

### A2. Start `weave-server`

```bash
aws ec2 start-instances \
  --region us-east-1 \
  --instance-ids i-0dea21dad454d0b31

aws ec2 wait instance-running \
  --region us-east-1 \
  --instance-ids i-0dea21dad454d0b31

aws ec2 describe-instances \
  --region us-east-1 \
  --instance-ids i-0dea21dad454d0b31 \
  --query 'Reservations[0].Instances[0].[State.Name,PublicIpAddress,IamInstanceProfile.Arn]' \
  --output text
```

Expect: `running`, public IP `52.0.130.62` (Elastic IP), and an instance profile ARN mentioning `WeaveEC2BedrockRole`.

### A3. Security group (SSH + app ports)

Allow (preferably **your current public IP**/32, not `0.0.0.0/0`):

| Port | Use |
|------|-----|
| 22 | SSH from your Mac |
| 5173 | Frontend |
| 8000 | Backend API |

Example (replace `sg-xxxxxxxx` and use your IP):

```bash
SG=sg-xxxxxxxx   # from describe-instances → SecurityGroups

MYIP=$(curl -s https://checkip.amazonaws.com)/32

aws ec2 authorize-security-group-ingress --region us-east-1 --group-id "$SG" \
  --protocol tcp --port 22 --cidr "$MYIP" 2>/dev/null || true
aws ec2 authorize-security-group-ingress --region us-east-1 --group-id "$SG" \
  --protocol tcp --port 5173 --cidr "$MYIP" 2>/dev/null || true
aws ec2 authorize-security-group-ingress --region us-east-1 --group-id "$SG" \
  --protocol tcp --port 8000 --cidr "$MYIP" 2>/dev/null || true
```

Do **not** open Postgres / Neo4j / Redis / Chroma to the internet.

### A4. SSH from that Mac

```bash
chmod 400 ~/.ssh/weave-server.pem

# Ubuntu AMI:
ssh -i ~/.ssh/weave-server.pem ubuntu@52.0.130.62

# Amazon Linux (if ubuntu user fails):
# ssh -i ~/.ssh/weave-server.pem ec2-user@52.0.130.62
```

---

## B. On the EC2 instance (after SSH)

### B1. Install Docker (once)

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker
docker --version
docker compose version
```

Prefer **≥ 40–60 GB** disk. `t3.large` (8 GiB RAM) is demo-tight; resize to `t3.xlarge` if Neo4j OOMs.

### B2. Git clone

**Public repo:**

```bash
cd ~
git clone https://github.com/saurabhdsh/scinova-os.git SciNova-OS
cd SciNova-OS
git checkout main
git pull
```

**Private repo** — GitHub PAT or SSH deploy key (do not paste secrets into chat):

```bash
git clone https://github.com/saurabhdsh/scinova-os.git SciNova-OS
# or: git clone git@github.com:saurabhdsh/scinova-os.git SciNova-OS
```

Confirm the commit you expect:

```bash
git log -1 --oneline
ls docs/deploy_ec2_bedrock.md backend/app/services/chem/
```

### B3. Create `.env` on the instance

On EC2 prefer the **IAM role** — omit access keys:

```bash
cd ~/SciNova-OS
nano .env
```

Minimum:

```bash
DEFAULT_LLM_PROVIDER=bedrock
ENABLED_LLM_PROVIDERS=bedrock
BEDROCK_ENABLED=true
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0
BEDROCK_ONTOLOGY_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0

SECRET_KEY=<long-random-string>
DEBUG=false
LOG_LEVEL=INFO

CORS_ORIGINS=http://52.0.130.62:5173,http://ec2-52-0-130-62.compute-1.amazonaws.com:5173
```

Optional: from the Mac, copy a sanitized `.env` (never commit it):

```bash
scp -i ~/.ssh/weave-server.pem .env ubuntu@52.0.130.62:~/SciNova-OS/.env
```

Then on EC2 remove `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` so the **instance role** is used.

### B4. Verify Bedrock via instance role

```bash
aws sts get-caller-identity
# Arn should mention WeaveEC2BedrockRole

chmod +x scripts/test-bedrock.sh
./scripts/test-bedrock.sh
```

### B5. Start the stack

```bash
cd ~/SciNova-OS
docker compose up -d --build
docker compose ps
docker compose logs -f backend
```

Browser:

- Frontend: `http://52.0.130.62:5173`
- API docs: `http://52.0.130.62:8000/docs`

---

## C. Back on the Mac — day-2

```bash
aws ec2 stop-instances --region us-east-1 --instance-ids i-0dea21dad454d0b31
aws ec2 start-instances --region us-east-1 --instance-ids i-0dea21dad454d0b31

# After SSH, refresh code:
#   cd ~/SciNova-OS && git pull && docker compose up -d --build
```

---

## Checklist

- [ ] Latest code **pushed to GitHub** from the machine that has MDS work
- [ ] AWS CLI Mac: instance **running**, EIP `52.0.130.62`, IAM role attached
- [ ] SG allows 22 / 5173 / 8000 from your IP
- [ ] SSH works with `.pem`
- [ ] `git clone` → expected commit
- [ ] `.env` Bedrock on; no static AWS keys (instance role)
- [ ] `./scripts/test-bedrock.sh` passes
- [ ] `docker compose up -d --build` healthy
- [ ] Login + one Bedrock LLM call works
- [ ] Molecular Studio works (local RNN)

---

## Related

- [`molecular_design_architecture.md`](molecular_design_architecture.md)
- [`molecular_discovery_studio_features.md`](molecular_discovery_studio_features.md)
- `scripts/test-bedrock.sh`
