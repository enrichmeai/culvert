# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x | ✅ |

## Reporting a vulnerability

Please **do not** open a public issue for suspected vulnerabilities.

Use GitHub's private vulnerability reporting on this repository
(Security → Report a vulnerability), which reaches the maintainer directly.
You should receive an acknowledgement within a few days.

## Scope notes

- Culvert's adapters execute with the credentials of the runtime service
  account you configure — least-privilege IAM per deployment is provided in
  each `deployments/*/terraform/` and is the recommended posture.
- No component ever transmits data to any endpoint other than the cloud
  services you configure. There is no telemetry.
- Secrets are never accepted via code or config files: cloud secret managers
  (via the `SecretProvider` contract) and workload identity are the supported
  mechanisms.
