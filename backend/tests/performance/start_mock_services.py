#!/usr/bin/env python
"""Start all mock services for performance testing.

Starts both mock LLM server and mock rerank server.
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.tests.performance.config import get_config


def start_mock_llm(port: int | None = None) -> subprocess.Popen:
    """Start mock LLM server."""
    config = get_config()
    port = port or config.mock_llm_port

    print(f"Starting mock LLM server on port {port}...")
    return subprocess.Popen(
        [sys.executable, "-m", "backend.tests.performance.mock_llm_server"],
        env={**subprocess.os.environ, "MOCK_LLM_PORT": str(port)},
    )


def start_mock_rerank(port: int | None = None) -> subprocess.Popen:
    """Start mock rerank server."""
    config = get_config()
    port = port or config.mock_rerank_port

    print(f"Starting mock rerank server on port {port}...")
    return subprocess.Popen(
        [sys.executable, "-m", "backend.tests.performance.mock_rerank_server"],
        env={**subprocess.os.environ, "MOCK_RERANK_PORT": str(port)},
    )


def wait_for_server(url: str, timeout: int = 30) -> bool:
    """Wait for server to be ready."""
    import httpx

    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = httpx.get(f"{url}/health", timeout=2)
            if response.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def main():
    parser = argparse.ArgumentParser(description="Start mock services for performance testing")
    parser.add_argument(
        "--llm-port",
        type=int,
        default=None,
        help="Port for mock LLM server",
    )
    parser.add_argument(
        "--rerank-port",
        type=int,
        default=None,
        help="Port for mock rerank server",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Don't start mock LLM server",
    )
    parser.add_argument(
        "--no-rerank",
        action="store_true",
        help="Don't start mock rerank server",
    )

    args = parser.parse_args()

    config = get_config()
    llm_port = args.llm_port or config.mock_llm_port
    rerank_port = args.rerank_port or config.mock_rerank_port

    processes = []

    try:
        if not args.no_llm:
            proc = start_mock_llm(llm_port)
            processes.append(("LLM", proc, f"http://localhost:{llm_port}"))

        if not args.no_rerank:
            proc = start_mock_rerank(rerank_port)
            processes.append(("Rerank", proc, f"http://localhost:{rerank_port}"))

        # Wait for servers to be ready
        print("\nWaiting for servers to be ready...")
        all_ready = True
        for name, proc, url in processes:
            if wait_for_server(url):
                print(f"  ✓ {name} server ready at {url}")
            else:
                print(f"  ✗ {name} server failed to start")
                all_ready = False

        if not all_ready:
            print("\nSome servers failed to start. Exiting.")
            for _, proc, _ in processes:
                proc.terminate()
            sys.exit(1)

        print("\nAll mock services are running. Press Ctrl+C to stop.")
        print("\nConfiguration for tests:")
        print(f"  LLM_BASE_URL=http://localhost:{llm_port}/v1")
        print(f"  RERANK_BASE_URL=http://localhost:{rerank_port}")
        print("  LLM_API_KEY=mock-key")
        print("  RERANK_API_KEY=mock-key")
        print("  RERANK_MODEL=mock-rerank-model")

        # Keep running until interrupted
        while True:
            # Check if processes are still alive
            for name, proc, _ in processes:
                if proc.poll() is not None:
                    print(f"\n{name} server exited unexpectedly with code {proc.returncode}")
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n\nShutting down mock services...")
    finally:
        for name, proc, _ in processes:
            print(f"  Stopping {name} server...")
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        print("Done.")


if __name__ == "__main__":
    main()
