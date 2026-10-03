# Box — Provider Cookbooks for Standing Up a Hermes Agent Box

A "box" is a cloud machine that runs the Hermes agent configured with this repository's stress dialogue loops and health workflows. Each provider subdirectory contains an agent-executable cookbook — point your agent (Zed agent, Claude Code, Hermes, Command Code, etc.) at the cookbook's markdown file, and it will execute the provisioning and configuration end-to-end, pausing only when human interaction is required (marked with ⛔).

### Why a Cloud Computer / VM?

Hermes is a **stateful daemon** — it runs an active gateway service, scheduled cron loops for proactive check-ins (e.g. morning HRV breaks or evening debriefs), persistent memories under `~/.hermes/`, and an interactive CLI environment. A persistent cloud computer or VM fits this continuous, stateful agent lifecycle, unlike request-driven ephemeral serverless functions.

### Available Providers

| Provider | Cookbook | Description |
|---|---|---|
| **Matrix OS** | [Matrix/](./Matrix/matrix-box-cookbook.md) | Cloud computer instance via the Matrix CLI (`@finnaai/matrix`), with persistent Hermes gateway and Matrix GUI desktop app integration |

To add another provider (e.g., Nebius, AWS, Hetzner), follow the same structure and contract: agent-executable workflow, explicit human stop-points, leak-clean commands, and teardown instructions.
