# Deployment Guide

## Deployment Modes

### Local Development (default)

**Best for:** Development, personal use, small teams

```bash
uv run agentplane run
```

- SQLite database
- Single process
- No external dependencies

### Team / Small Production

**Best for:** Teams, moderate load

Switch to PostgreSQL:

```bash
export AGENTPLANE_DATABASE_URL="postgresql+asyncpg://user:pass@localhost/agentplane"
agentplane init
agentplane run --host 0.0.0.0
```

### Production

**Best for:** High availability, many agents

Architecture:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Nginx     │────▶│  Uvicorn    │────▶│ PostgreSQL  │
│  (reverse)  │     │  workers    │     │             │
└─────────────┘     └─────────────┘     └─────────────┘
```

Run with Gunicorn + Uvicorn workers:

```bash
gunicorn agentplane.api.main:app \
  -w 4 \
  -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:3400
```

### Docker (optional)

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml .
RUN pip install uv && uv sync

COPY . .
CMD ["uv", "run", "agentplane", "run", "--host", "0.0.0.0"]
```

### Scaling Strategies

| Bottleneck | Solution |
|---|---|
| Single server | Deploy multiple instances behind a load balancer |
| Database | Upgrade to PostgreSQL with connection pooling |
| Adapter execution | Use remote execution targets or cloud adapters |
| Storage | Move `./data` to persistent volume / S3 |

## Security Checklist

- [ ] Change default SQLite path for production
- [ ] Use PostgreSQL with strong credentials
- [ ] Run behind a reverse proxy (Nginx, Caddy)
- [ ] Enable HTTPS
- [ ] Set `AGENTPLANE_DEBUG=false`
- [ ] Restrict agent API keys (if implementing auth layer)
