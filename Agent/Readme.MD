This folder contains a small Python agent that fetches CNN's current homepage headlines.

Files:
- `headline_agent.py`: fetches `https://www.cnn.com` and extracts up to 5 headlines.
- `test_headline_agent.py`: unit tests for the extraction logic.

Usage:

```bash
python3 Agent/headline_agent.py
```

Default output is one title per line, up to 5 lines.

Offline usage:

```bash
python3 Agent/headline_agent.py --html-file Agent/sample_homepage.html
python3 Agent/headline_agent.py --html-file Agent/sample_homepage.html --json
```

Tests:

```bash
python3 -m unittest Agent/test_headline_agent.py
```

The script uses only Python's standard library.
