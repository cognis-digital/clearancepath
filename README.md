# CLEARANCEPATH — Personnel clearance hygiene tracker — SF-86, SEAD-3/4, training currency

> Part of the **[Cognis Neural Suite](https://github.com/cognis-digital)** by [Cognis Digital](https://cognis.digital)
> MIT License · domain: `federal`

[![PyPI](https://img.shields.io/pypi/v/cognis-clearancepath.svg)](https://pypi.org/project/cognis-clearancepath/)
[![CI](https://github.com/cognis-digital/clearancepath/actions/workflows/ci.yml/badge.svg)](https://github.com/cognis-digital/clearancepath/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Personnel clearance hygiene tracker — SF-86, SEAD-3/4, training currency.

## Install

```bash
pip install cognis-clearancepath
```

For local development from this repo:

```bash
pip install -e .
```

## Quick start

```bash
clearancepath --version
clearancepath scan demos/                          # run against bundled demo
clearancepath scan demos/ --format sarif --out r.sarif --fail-on high
clearancepath mcp                                   # start as MCP server (Cognis.Studio / Claude Desktop / Cursor)
```

## Built-in demo scenarios

Every scenario folder includes a `SCENARIO.md` describing what it represents and what findings to expect.

- `demos/01-overdue-sead3/` — see [`SCENARIO.md`](demos/01-overdue-sead3/SCENARIO.md)
- `demos/02-training-quarterly-review/` — see [`SCENARIO.md`](demos/02-training-quarterly-review/SCENARIO.md)
- `demos/03-clean-program/` — see [`SCENARIO.md`](demos/03-clean-program/SCENARIO.md)

## How it fits the Cognis Neural Suite

This tool is one of 52 in the [Cognis Neural Suite](https://github.com/cognis-digital). The full suite + launcher lives at:

- Suite landing: https://cognis.digital
- All 52 repos: https://github.com/cognis-digital
- Cognis.Studio (Enterprise AI Workforce, MCP host): https://cognis.studio

Every Suite tool ships an MCP server, so Cognis.Studio agents can call them as scoped capabilities.

## License

MIT. See [LICENSE](LICENSE).

## About

**[Cognis Digital](https://cognis.digital)** — Wyoming, USA · *Making Tomorrow Better Today: Advanced Cybersecurity, AI Innovation, and Blockchain Expertise.*
