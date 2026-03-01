# video-skill-extractor

Scaffold repo for extracting structured markdown steps from course recordings.

## Quickstart

```bash
make install
make verify
```

## CLI

```bash
uv run video-skill --help
```

## Self-hosted model stack (reasoning + VLM + ASR)

### 1) Download models (HF CLI)

```bash
./scripts/bootstrap_models.sh
```

### 2) Launch model services (Docker Compose)

```bash
docker compose -f deploy/docker-compose.models.yml up -d
```

### 3) Configure provider endpoints

```bash
cp config.example.json config.json
# edit base_url values to your server IP
```

### 4) Validate and ping providers

```bash
uv run video-skill config-validate --config config.json
uv run video-skill providers-ping --config config.json --path /v1/models
```
