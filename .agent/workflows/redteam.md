You are a hostile reviewer with fresh eyes. Review the diff of the last phase (git diff <phase-start-tag>..HEAD).
Find: (a) bugs and unhandled edge cases, (b) security holes (sandbox escape, secret leakage, command injection, SSRF, path traversal), (c) places the code lies about success (swallowed errors, fake data), (d) drift from AGENTS.md or contracts, (e) missing tests. 
Output a prioritized list with file:line. Then FIX every P0/P1 issue with tests, re-run all verification commands, commit as `fix: redteam phase N`.
