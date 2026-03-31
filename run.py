"""Entry point: starts the FastAPI server."""
import os
import uvicorn
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    is_prod = bool(os.getenv("DATABASE_URL"))
    host = "0.0.0.0" if is_prod else "127.0.0.1"
    print(f"Trading Dashboard starting at http://{host}:{port}")
    uvicorn.run(
        "backend.app:app",
        host=host,
        port=port,
        reload=not is_prod,
        reload_dirs=[str(Path(__file__).parent)] if not is_prod else None,
    )
