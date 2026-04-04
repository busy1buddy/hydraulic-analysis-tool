# Next Instructions — API bridge rewrite

Quality: ACCEPTABLE

Add 'anthropic>=0.40.0' to requirements.txt (insert alphabetically in scientific section). Improve error messages on lines 135-136 to say 'ANTHROPIC_API_KEY environment variable not set. Add to .env file or run: set ANTHROPIC_API_KEY=sk-ant-...' Then run: python -m pytest tests/ -q to confirm no regressions. No further changes needed â€” the API bridge design is sound.
