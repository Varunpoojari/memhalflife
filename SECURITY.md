# Security Policy

MemHalfLife is a research tool for analysing memory images in a lab. It parses Volatility 3 output, scenario files and YARA rules, so please treat any input you did not create yourself as untrusted.

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x (`main`) | Yes |
| Older | No |

## Reporting a vulnerability

Please **do not open a public issue** for security problems.

Report privately through GitHub's [private vulnerability reporting](https://github.com/Varunpoojari/memhalflife/security/advisories/new) (Security tab, then "Report a vulnerability").

Please include:

- what is affected (a file, function or command)
- steps to reproduce, with a minimal input file if possible
- the impact you expect (for example code execution, path traversal, or a crash on crafted Volatility output)

I aim to acknowledge reports within 7 days and to agree a fix and disclosure timeline with you before anything is made public. Credit is given in the release notes unless you would rather stay anonymous.

## Scope

In scope:

- parsing of Volatility 3 JSON, scenario TOML and YARA rule files
- the `memhalflife` command-line tool and report generation
- handling of file paths and output locations

Out of scope:

- vulnerabilities in Volatility 3, YARA or other third-party dependencies (please report those upstream)
- the malware or attack scenarios being studied, which are expected to be malicious by design
- findings that need an already-compromised analysis machine

## Safe use

- Run lab scenarios only in isolated virtual machines you own.
- Do not analyse memory images containing other people's data without permission.
- Keep dependencies up to date (`pip install -U`).
