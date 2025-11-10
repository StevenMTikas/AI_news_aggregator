#!/usr/bin/env python
"""
Quick start script for the AI News Aggregator web interface.
Run this from the root directory to start the web server with optimal settings.
"""
import sys
import os
from pathlib import Path


def main():
    """Main function to start the web server"""
    env_path = Path('.env')
    if not env_path.exists():
        print("⚠️  Warning: No .env file found!")
        print(f"Please create a .env file in the root directory")
        print("\nExample content:")
        print("  OPENAI_API_KEY=sk-your-key-here")
        print("  SERPER_API_KEY=your-serper-key-here")
        response = input("\nContinue anyway? (y/N): ")
        if response.lower() != 'y':
            sys.exit(1)

    print("🚀 Starting AI News Aggregator Web Interface...")
    print("📍 Server will be available at: http://localhost:8000")
    print("🛑 Press Ctrl+C to stop the server\n")

    try:
        import uvicorn
        # Use reload=False on Windows to avoid multiprocessing issues
        # For development with auto-reload, run: uvicorn app:app --reload
        uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
    except ImportError:
        print("❌ Error: uvicorn not installed")
        print("Please run: pip install -e .")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped. Goodbye!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # This guard is required for Windows multiprocessing compatibility
    main()

