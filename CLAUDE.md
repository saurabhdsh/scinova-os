# SciNova OS — Claude Code Context

## Stack
Docker · Node · React · Express

## Quick start
```bash
# Install and run — adjust for detected stack
npm install && npm run dev
```

## Architecture
- **Source:** backend/app/__pycache__, backend/app/core/__pycache__, backend/app/dependencies/__pycache__, backend/app/models/__pycache__, backend/app/routes/__pycache__, backend/app/services/__pycache__, backend/app/tasks/__pycache__, backend/app/services, frontend/src/pages, backend/app, frontend/src/components/shell, backend/app/routes, frontend/src/components/admin, backend/app/models, frontend/src/components/workflow, frontend/src/components/agents, frontend/src/components/workspace, frontend/src/components/graph, frontend/src/api, scripts/lib, frontend/src, frontend/src/components/ui, frontend/src/context, backend/app/dependencies, frontend/src/lib, backend/app/core, backend/app/tasks, frontend/src/components/brand
- **Tests:** test directories
- **Docs:** docs

## Token budget
- Total estimated workspace tokens: ~21,56,469
- Always scope file reads to the module under change
- Never load: backend/venv, frontend/node_modules, backend/app/routes/__pycache__, frontend/dist, backend/app/routes

## Safety
Do not read or echo: .env, .env.example

See `.claude/context-policy.md` for full rules.
