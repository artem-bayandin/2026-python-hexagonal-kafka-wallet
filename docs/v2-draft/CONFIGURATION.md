| `production` | Future controlled deployment only. | Demo OTP output, static admin access, and Kafka diagnostics are disabled and cannot be enabled. |

| `ENABLE_KAFKA_DIAGNOSTICS` | No | `false` | May be `true` only in development and only in version 2. |
| `KAFKA_BOOTSTRAP_SERVERS` | Version 2 | None | Comma-separated broker addresses. |
| `KAFKA_COMMAND_TOPIC` | No | `wallet.commands.v1` | One partition key per target user ID. |
| `KAFKA_WORKER_GROUP_ID` | No | `wallet-command-worker-v1` | One worker consumer group. |

| `VITE_OPERATION_POLL_INITIAL_MS` | No | `2000` | Version-2 operation polling initial delay. |
| `VITE_OPERATION_POLL_MAX_MS` | No | `10000` | Exponential backoff ceiling. |

| Kafka | Internal Compose network by default; do not expose a host port unless required for local debugging. |

- Redact all secret values, JWTs, OTPs, admin keys, and database/Kafka connection strings from logs, traces, error responses, and diagnostics records.
