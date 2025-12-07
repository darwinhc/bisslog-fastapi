# bisslog-fastapi

![PyPI - Version](https://img.shields.io/pypi/v/bisslog-fastapi?style=flat-square&color=blue)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**Framework-agnostic adapter for Bisslog.**
Connects external interfaces to use cases while keeping domain logic isolated and pure.

`bisslog-fastapi` is the **FastAPI adapter** for the Bisslog hexagonal architecture framework. It allows you to expose your core business logic (Use Cases) as HTTP/WebSocket endpoints automatically, preserving the Clean Architecture principles.

It acts as a bridge:
1.  **Read Metadata**: Scans your Bisslog services and triggers.
2.  **Adapt**: Maps HTTP requests (Path, Query, Body, Headers) to your Use Case input arguments.
3.  **Execute**: Runs your Use Case (Sync or Async).
4.  **Respond**: formats the result back to JSON.

## Installation

```bash
pip install bisslog-fastapi
```

## Usage

You can use `bisslog-fastapi` in two ways: as a **Runtime Runner** or as a **Code Generator (Builder)**.

### 1. Runtime Runner (Recommended for Dev)

Dynamically mounts your use cases at startup without generating extra code files.

```bash
bisslog_fastapi run [--metadata-file FILE] [--use-cases-folder-path DIR]
                    [--infra-path DIR] [--encoding ENC]
                    [--host HOST] [--port PORT] [--reload]
                    [--workers WORKERS] [--log-level LEVEL]
```

Example:
```bash
bisslog_fastapi run --metadata-file bisslog.metadata.json --port 8000 --reload
```

### 2. Builder Strategy (Production)

Generates a static `main.py` file with all routes hardcoded. This is useful for inspection or performance optimization.

```bash
bisslog_fastapi build [--metadata-file FILE] [--use-cases-folder-path DIR]
                      [--infra-path DIR] [--encoding ENC]
                      [--target-filename FILE]
```

Example:
```bash
bisslog_fastapi build --target-filename main.py
```

Then run the generated file normally with uvicorn:

```bash
uvicorn main:app --reload
```

## Features

-   **Automatic Routing**: Uses `TriggerHttp` metadata to register routes.
-   **Smart Mapping**:
    -   `path_query.*` → URL Path parameters.
    -   `body.*` → JSON Body fields.
    -   `params.*` → Query parameters.
    -   `headers.*` → HTTP Headers.
-   **Async Support**: Native support for asynchronous Use Cases.
-   **OpenAPI Integration**: Automatically generates Swagger UI for your domain logic with correct signatures.
-   **CORS**: Configurable per-trigger via metadata.


## License

This project is licensed under the MIT License.  
See the [LICENSE](LICENSE) file for details.
