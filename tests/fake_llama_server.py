"""Stand-in for llama-server in tests: accepts the same CLI (--port ...) and serves tests/mock_llama.
Use with: LLAMA_SERVER_CMD="python tests/fake_llama_server.py"
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("LOAD_DELAY", "2")
import uvicorn
from mock_llama import app

port = int(sys.argv[sys.argv.index("--port") + 1])
uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
