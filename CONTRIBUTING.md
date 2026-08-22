# Contributing to READIN

READIN welcomes narrowly scoped, auditable contributions.

## Development

```shell
uv sync --dev
make check
```

Before changing a contract, open an issue describing the semantic change, compatibility impact,
negative cases, and migration path. Contract changes must include positive and negative tests.

## Pull requests

- Keep changes inside the READIN repository.
- Preserve observation, claim, belief, forecast, and authority boundaries.
- Do not add live credentials, scraped private data, personal datasets, or generated evidence dumps.
- Retain failures, counterevidence, missingness, and abstentions.
- Describe what was validated and what remains unverified.

## Responsible collection

Adapters for human-related entities must document source authorization, access policy, licensing,
collection limits, retention, and audit behavior. Covert interception, credential bypass, stalking,
targeting, and action automation are out of scope.
