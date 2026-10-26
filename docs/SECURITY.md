# Security Policy & Execution Model — Receipt

## Core Principles

1. **Hostile Code Assumption**: Every pull request authored or modified by an agent is treated as potentially hostile or unsafe code. Untrusted code must never execute in the host environment without containment.
2. **Layered Isolation**:
   - **Docker Sandbox**: Container isolation with read-only root filesystems where feasible, non-root execution, CPU and RAM constraints, process limits (`pids-limit`), short wall-clock timeouts, and empty tmpfs mounts.
   - **Subprocess Fallback**: When Docker is not available, executes within isolated temporary directories with clean environment scrubbing (no API keys, tokens, or ambient credentials), strict timeouts, and restricted file permissions.
3. **Network Separation**:
   - **Prepare Phase**: Package dependency fetching may access the network (or package cache), strictly isolated from the testing runtime.
   - **Execute Phase**: Test execution and mutation evaluation operate with network access disabled (`--network none`).
4. **Credential Protection**:
   - No API keys, GitHub tokens, or system credentials are leaked or injected into sandbox execution containers.
   - Environment variables are scrubbed and only explicit whitelisted runtime flags are provided.
5. **Prompt Injection Hardening**:
   - Code diffs, commit messages, and PR descriptions are ingested purely as data, wrapped in unambiguous structural boundaries.
   - Output parsers validate strictly against typed Pydantic models; any prompt injection attempting to coerce verdict or score cannot alter hard gates.
