# Python Code Execution Service

A secure, sandboxed API to execute arbitrary Python code, built with Flask, Docker, and nsjail.

## Project Overview

This service provides a REST API endpoint `POST /execute` that accepts a Python script, executes it in a secure sandbox, and returns the result of the `main()` function along with `stdout`.

## How it works (my explanation)

At a high level, I built a small execution engine around a single endpoint:
- When a client calls `POST /execute` with a JSON body containing a `script` field, the API first parses the code with `ast` to make sure there is a `main()` function.
- I then wrap the user script in a small helper program that runs `main()`, captures anything printed to the console, and checks that the return value is JSON-serializable.
- This wrapped script is written to `/tmp` and executed inside an `nsjail` sandbox so the code has no network access, only a writable `/tmp`, and is limited in time and memory.
- After execution, the API responds with a JSON object containing the return value in `result` and all captured prints in `stdout`.

**Key Features:**
- **Sandboxed Execution**: Uses [nsjail](https://nsjail.dev/) to isolate code execution (filesystem, network, and resource limits).
- **Input Validation**: Ensures the script contains a `main()` function using AST parsing.
- **JSON Output**: Captures return values and standard output.
- **Cloud Ready**: Designed for Google Cloud Run.

## Local Setup & Running

### Prerequisites
- Docker installed

### Build the Image
```bash
docker build -t python-executor .
```

### Run the Service
Run the container (requires `--privileged` for nsjail user namespaces):
```bash
docker run --privileged -p 8080:8080 python-executor
```

## API Usage

### Endpoint
`POST /execute`

### Request Body
```json
{
  "script": "def main():\n    return {\"status\": \"ok\"}"
}
```

### Example cURL
```bash
curl -X POST http://localhost:8080/execute \
  -H "Content-Type: application/json" \
  -d '{
    "script": "def main():\n    import pandas as pd\n    print(\"Analyzing...\")\n    return {\"status\": \"success\", \"value\": 42}"
  }'
```

### Expected Response
```json
{
  "result": {"status": "success", "value": 42},
  "stdout": "Analyzing...\n"
}
```

## Google Cloud Run Deployment

1. **Submit Build**
   Replace `PROJECT_ID` with your Google Cloud Project ID.
   ```bash
   gcloud builds submit --tag gcr.io/PROJECT_ID/python-executor
   ```

2. **Deploy**
   ```bash
   gcloud run deploy python-executor \
     --image gcr.io/PROJECT_ID/python-executor \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated \
     --execution-environment=gen2
   ```
   *Note: `execution-environment=gen2` is recommended for better compatibility with sandboxing tools.*

### Test Cloud Endpoint
```bash
curl -X POST https://python-executor-293095667468.europe-west1.run.app/execute \
  -H "Content-Type: application/json" \
  -d '{
    "script": "def main():\n    return \"Hello from Cloud Run\""
  }'
```

## Implementation Details

- **Flask App (`app.py`)**: Handles API requests, validates scripts with `ast`, and orchestrates `nsjail` execution.
- **Sandbox (`nsjail.cfg`)**: Configures the isolation environment:
  - Read-only root filesystem (secure).
  - Writable `/tmp` (for script execution).
  - No network access.
  - 10s time limit, 512MB memory limit.
- **Dockerfile**: Multi-stage build:
  - Stage 1: Compiles `nsjail` from source.
  - Stage 2: Minimal runtime image (`python:3.11-slim`) with necessary dependencies.

## Benchmark
Time taken to complete challenge: ~1 hour 38 minutes.
