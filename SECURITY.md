# Security Policy

## Supported version

The current `0.x` branch receives security fixes while the public APIs stabilize.

## Reporting vulnerabilities

Please report vulnerabilities privately to the repository maintainers instead of opening a public issue containing exploit details.

## Security model

LeafRoute performs local parsing and retrieval by default. Optional reasoning providers can transmit selected candidate/evidence text to configured external services.

Applications are responsible for authentication, authorization, tenant isolation, encryption, secrets management, upload policy, and network egress controls.

## Offline mode

Use `LeafRouteConfig(mode="offline", offline=True)` or the CLI `--offline` option to prevent configured provider escalation. The runtime raises an explicit error if remote answer generation is attempted in offline mode.

## Untrusted documents

Treat document text as untrusted data. LeafRoute does not execute code or commands found in documents. Applications combining LeafRoute with agents or tools must ensure retrieved text cannot override system/tool policies.

## File handling

Do not compile files from untrusted users under a highly privileged operating-system account. Apply normal file-size and resource controls around any public upload endpoint.
