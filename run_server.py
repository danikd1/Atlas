#!/usr/bin/env python3
"""
Скрипт для запуска веб-сервера.

Использование:
    python3 run_server.py
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "src.web_server:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
        log_level="info"
    )

