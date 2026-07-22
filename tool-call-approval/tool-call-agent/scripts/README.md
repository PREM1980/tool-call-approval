# AIP direct-call script

`aip_chat.py` calls the OpenAI-compatible AIP endpoint directly, without the
agent graph, API gateway, UI, or third-party Python packages. It loads
`tool-call-agent/.env` automatically.

From `tool-call-agent/`:

```bash
python3 scripts/aip_chat.py "List all pods in the default namespace"
```

Optional overrides:

```bash
python3 scripts/aip_chat.py --model gpt-oss-120b --system "You are concise." "Hello"
```

The script uses `BASE_URL`, `MODEL_ID`, `OPENAI_API_KEY`, `LOCAL_VERIFY_SSL`,
and `LOCAL_CA_BUNDLE` from `.env`. It never prints the API key.
