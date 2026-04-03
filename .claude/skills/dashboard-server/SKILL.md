---
name: Dashboard Server
description: Use when the user asks to start, launch, check, or debug the web dashboard. Manages the FastAPI server and Preview MCP integration.
---

# Managing the Dashboard Server

## Starting the Dashboard

### Via Claude Preview MCP (preferred)
The server is pre-configured in `.claude/launch.json` as `epanet-dashboard`.
Use `preview_start` with name `epanet-dashboard` to launch on port 8765.

### Via Command Line
```bash
python server.py
# Dashboard at http://localhost:8765
```

## Health Check
```bash
curl http://localhost:8765/api/networks
# Should return: {"networks": ["australian_network.inp", ...]}
```

## API Endpoints
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/` | Dashboard HTML page |
| GET | `/api/networks` | List .inp files from models/ |
| GET | `/api/network/{file}` | Network topology + details |
| GET | `/api/steady/{file}` | Run steady-state analysis |
| POST | `/api/transient` | Run water hammer analysis |
| POST | `/api/joukowsky` | Joukowsky pressure calculator |

## Debugging
- **Port conflict**: Check if 8765 is already in use
- **Server won't start**: Check Python encoding (`sys.stdout` UTF-8 wrapper)
- **Dashboard blank**: Check browser console for Plotly.js CDN loading errors
- **Analysis fails with 400**: Check server stderr for Python traceback - usually wrong valve name or missing network file
- **Preview MCP timeout**: Plotly.js CDN may be slow to load; use `preview_snapshot` instead of `preview_screenshot` for text verification

## Dashboard Tabs
1. **Steady-State**: Select network -> Run -> View pressures, flows, compliance
2. **Transient**: Set params (valve, closure time, wave speed) -> Run -> View surge, mitigation
3. **Joukowsky**: Quick dH = (a x dV) / g calculator with pipe material presets
