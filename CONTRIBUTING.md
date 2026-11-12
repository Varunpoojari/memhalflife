# Contributing to MemHalfLife

Thanks for your interest. MemHalfLife is a defensive research tool for measuring how long fileless and living-off-the-land evidence survives in memory. Scenarios, YARA rules, statistics and docs are all good places to help.

## Ground rules

- The tool only **reads** memory images. Contributions must not add code that generates or runs attack payloads.
- Scenario notes should point to published tests (for example Atomic Red Team) and assume an isolated lab with harmless test programs.
- Synthetic data must always stay clearly labelled as synthetic.
- For security problems in the tool itself, follow [SECURITY.md](SECURITY.md) instead of opening a public issue.

## Development setup

```bash
git clone https://github.com/Varunpoojari/memhalflife.git
cd memhalflife
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e ".[dev,yara]"
pytest
```

Installing the `yara` extra matters: without it the YARA tests are skipped, so a passing run does not cover them.

## Adding a scenario

1. Copy a shipped file in `scenarios/` as a starting point.
2. Define the artefacts, weights and regex conditions, and note the ATT&CK technique and platform.
3. If you add detection logic, add a rule in `rules/yara/` with a positive and a benign test.
4. Add or update tests in `tests/`.
5. Mention the scenario in the README table.

## Pull request process

1. Fork the repository and create a branch from `main` (for example `scenario/s07-dll-sideload` or `fix/bootstrap-ci`).
2. Keep each pull request to one change.
3. Run `pytest` and make sure it passes before opening the pull request.
4. Update `docs/` when you change methodology, scoring or acquisition guidance.
5. Describe what changed, why, and how you verified it.

## License

By contributing you agree that your contributions are licensed under the project's [MIT License](LICENSE).
