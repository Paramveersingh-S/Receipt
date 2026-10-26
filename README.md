# RECEIPT

> **Proof, not promises, for agent-written code.**
> Receipt verifies that an AI agent's pull request is *actually* done — with evidence — and remembers every lesson your repo learned the hard way (**Scar Tissue**) so the next agent starts warm.

## Overview
Receipt consists of two interconnected engines:
1. **Scar Tissue (Institutional Memory)**: Learns constraints from repo history (review comments, reverts, incident fixes), serves them to agents via MCP, and checks diffs against them.
2. **Receipt (Verification Engine)**: Verifies an agent PR in a sandbox (fail-before/pass-after tests, mutation score on changed lines, constraint checks, regression suite, browser QA), loops failures back for repair, and outputs an evidence receipt.

## Quickstart
```bash
cp .env.example .env
make mock # Launch mock API server for UI development and testing
make test # Run backend test suite
```
