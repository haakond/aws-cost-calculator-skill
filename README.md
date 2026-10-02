# Agent skill: aws-cost-calculator

Build [AWS Pricing Calculator](https://calculator.aws) estimates from your Terraform, design documents or a list of services, using the coding agent you already work in. Works with Claude Code, Kiro, Cursor and any other agent that supports Agent Skills and MCP.

- **Output:** a shareable `calculator.aws` link, plus a markdown file with every input and assumption behind the estimate. The file is written before the estimate is built, so it can go into git alongside the code it describes.
- **Input:** Infrastructure as Code (Terraform, CloudFormation, CDK), design documents or a list of services. The agent asks for usage figures it cannot find and marks any it has to estimate.
- **Cost:** free. No AWS credentials needed.
- **Requirements:** Node.js and the AWS Pricing Calculator MCP server (installed with the plugin).
- **Setup:** Claude Code plugin, Kiro Power or Cursor plugin. See [Quick start](#quick-start).

## Challenges this solution addresses

Most AWS estimates are still built by hand in the [calculator](https://calculator.aws/)'s web UI. That has some well-known problems:

- **Manual and slow.** Services are added by clicking through forms, field by field, although the architecture already exists as Terraform or a design document.
- **Not reproducible.** The inputs live in a browser session and in someone's head. Another person, or the same person later, gets a different estimate, and the reasoning behind each number is not recorded.
- **Not scriptable.** The public calculator (`calculator.aws`) has no official API for creating estimates.
- **Incomplete by default.** The calculator does not prompt for common cost lines (root volumes, data transfer, backup storage, Multi-AZ, support plan) and does not model some billing details, such as management fees or minimum storage durations on archival tiers.
- **Unreliable when delegated to an AI.** Without tooling, an agent recalls prices from training data or scrapes pricing pages that render client-side. The numbers look authoritative but are not current, and no estimate exists that anyone can open.

## Why the output is a calculator estimate

- **It is easy to share.** A `calculator.aws` link can be sent to a customer or passed between teams in pre-sales, and the recipient can open and adjust it. A markdown table or a spreadsheet cannot be verified or edited the same way.
- **It is a common format.** Customers, AWS account teams and AWS Partners all work with calculator links, so the estimate does not have to be explained or rebuilt in someone else's tool.
- **AWS Partner processes require it.** For AWS Partners, Partner Central processes such as funding requests and opportunity deal sizing expect a Pricing Calculator estimate, and Partner Central can [import a calculator link](https://aws.amazon.com/about-aws/whats-new/2025/12/aws-partner-central-opportunity-deal-sizing) directly. A custom calculation rendered as markdown is not accepted there.

## How it works

The agent builds the estimate through an MCP server and follows the same steps every time:

1. **Inventory:** it lists the services from the Terraform plan, design document or user-supplied list, and asks for usage figures that were not given.
2. **Fact check:** it checks the design against current AWS documentation (AWS Knowledge MCP server) for cost components the calculator does not model, commitment-versus-workload mismatches and storage-class constraints.
3. **Record the basis:** it writes a markdown file (`cost-estimate/<name>.md` by default) with the sources, the plan table, an assumptions table that marks each input as confirmed or estimated, and the documentation findings. This happens before anything is built.
4. **Confirm:** it presents the plan table (service, sizing, key assumption) and waits for approval before anything is written to `calculator.aws`.
5. **Build:** it creates the estimate, validates it, and returns the shareable `calculator.aws` link. An estimate without a link is not considered done.
6. **Finalize:** it updates the same file with the link, the validation result, a second documentation check of the built estimate and a history row, and checks a list of commonly missed cost lines.

The basis file is plain markdown inside the project. Committed before and after the build, its git history is the changelog of the estimate: a changed assumption appears as a diff, and each rebuild adds a history row with its new link. The agent writes the file but never commits or pushes it.

### Sequence

Installing the plugin registers the skill and both MCP servers with the agent. At the start of each session the agent loads only the skill's name and description. The full instructions load when a request matches, or when the skill is invoked by name.

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Agent as Agent (Claude Code, Kiro, Cursor etc.)
    participant Skill as aws-cost-calculator skill
    participant Calc as AWS Calculator MCP server
    participant Know as AWS Knowledge MCP server
    participant Basis as Basis file in the project
    participant Web as calculator.aws

    User->>Agent: Estimate the cost of ./infra
    Agent->>Skill: Request matches the skill description, load SKILL.md
    Agent->>Agent: Read Terraform, plan output or design documents
    Agent-->>User: Ask for usage figures that are missing
    User->>Agent: Provide figures, or accept stated estimates
    Agent->>Calc: search_services, get_service_fields (read-only)
    Agent->>Know: Search AWS documentation for gaps in the cost model
    Agent->>Basis: Write sources, plan, assumptions and findings (draft)
    Agent-->>User: Plan table with sizing, assumptions and findings
    User->>Agent: Confirm the plan
    Agent->>Basis: Mark the basis as confirmed
    Agent->>Calc: create_estimate and add_service
    Calc->>Web: Write draft estimate
    Agent->>Calc: validate_estimate
    Agent->>Calc: export_estimate
    Calc-->>Agent: Shareable calculator.aws link
    Agent->>Know: Second check of the final estimate
    Agent->>Basis: Add link, findings and history row (built)
    Agent-->>User: Link and basis file location
```

The basis file exists before the build, and nothing is written to `calculator.aws` until the user confirms the plan (message 10). The user can commit the basis file before and after the build.

| Agent | Automatic | By name |
|---|---|---|
| Claude Code | When the request matches the skill description | `/aws-cost-calculator:aws-cost-calculator` |
| Kiro | When the request matches the Power keywords or the skill description | `/aws-cost-calculator` |
| Cursor | When the request matches the skill description | Type `/` in Agent chat and search for `aws-cost-calculator` |

### Example

Illustrative; services, figures and the link are placeholders.

```text
You:    Estimate the monthly cost of this Terraform plan in eu-west-1.
        Peak load is about 50 requests per second.

Agent:  Basis written to cost-estimate/orders-platform.md (status: draft).
        Planned estimate. Please confirm before I create it:

        | Service        | Sizing                               | Key assumption                    |
        |----------------|--------------------------------------|-----------------------------------|
        | ALB            | 1 load balancer                      | 50 req/s peak (confirmed)         |
        | ECS Fargate    | 2 tasks, 0.5 vCPU / 1 GB             | Running 24/7 (estimated)          |
        | RDS PostgreSQL | db.t4g.medium, Multi-AZ, 100 GB gp3  | Multi-AZ as in the Terraform plan |

        Documentation check: <findings, for example cost lines the calculator does not model>

You:    go

Agent:  Estimate created and validated: https://calculator.aws/#/estimate?id=<id>
        Basis updated: cost-estimate/orders-platform.md (status: built).
        Commit it to keep the estimate's history in git.
```

## How to use it

Point your agent at whatever describes the solution: Terraform code, plan or state output, design documents, README files or architecture decision records. It identifies the AWS services and builds the estimate from there. For example:

```text
Analyze the Terraform in ./infra and produce an AWS Pricing Calculator estimate for eu-west-1.
Read docs/solution-design.md and estimate the monthly cost of the proposed architecture.
Estimate the production environment from this plan output, assuming 200 GB of data transfer per month.
```

The agent asks for any usage figures the material does not contain (request rate, data volume, run hours) before it builds anything, and it shows the plan table for approval first.

### Typical use cases

1. **Cost check on Terraform before it ships.** Estimate a new module or environment from the code or the plan, so cost is reviewed alongside the change instead of after the first bill.
2. **Baselining an existing deployment.** Estimate the running cost of an environment from its Terraform, for a handover, a managed-service price or a budget conversation.
3. **Comparing design options.** Run the skill once per option (for example single-AZ against Multi-AZ, or Fargate against EKS) and compare the resulting estimates, each with its own listed assumptions.
4. **Pre-sales proposals.** Turn a design document or architecture description into a `calculator.aws` link that can be sent to the customer and adjusted together with them.
5. **AWS Partner funding and opportunities.** Produce the Pricing Calculator estimate that MAP and POC requests attach, or that Partner Central imports for deal sizing, without re-typing the architecture into the UI.

## Benefits

| | Manual calculator | With this skill |
|---|---|---|
| Entering services | Re-typed in the UI, field by field | Taken from Infrastructure-as-Code or design document; the user reviews a table instead of filling forms |
| Reproducibility | Depends on the person | The same workflow every time, with every assumption listed and labelled confirmed or estimated |
| Traceability | Inputs are not recorded; a changed number cannot be explained later | A basis file in the project, written before the build; git history shows what changed between estimates |
| Verifiability | A total, possibly with a link | A `calculator.aws` link produced with AWS-calculated pricing, plus the assumptions table |
| Completeness | Whatever the user remembers | A fixed checklist of commonly missed cost lines, and documentation checks for gaps in the calculator's own model |
| Re-estimating after a change | Change and click in the UI | Change the input and re-run |

## Who it is for

- **Solutions Architects** estimating the cost of an AWS solution or a proposed design
- **Pre-sales engineers** who need an estimate that can be handed to a customer or reviewed internally
- **AWS Partner teams** preparing estimates for Partner Central processes such as opportunity deal sizing and funding requests
- Anyone who keeps an architecture in Terraform or a design document and needs the matching `calculator.aws` estimate

## Before installing

- The calculator MCP server is an AWS sample project that uses undocumented calculator APIs. It may change or break without notice.
- Estimates are planning figures, not AWS quotes. Every estimated input is listed in the assumptions table and should be reviewed.
- The AWS Knowledge MCP server used for the fact check is hosted by AWS, rate-limited, and receives the documentation queries the skill sends. Without it the skill still runs, but states that the architectural reasoning was not independently checked.

## Quick start

The skill depends on two MCP servers: [`aws-pricing-calculator-mcp-server`](https://github.com/aws-samples/sample-aws-pricing-calculator-mcp) (builds the estimate, required) and the [AWS Knowledge MCP server](https://awslabs.github.io/mcp/servers/aws-knowledge-mcp-server) (documentation fact check, strongly recommended). Neither needs AWS credentials. [Node.js](https://nodejs.org/en/download) is required for the calculator server. The Claude Code, Kiro and Cursor routes below install the skill and both servers together.

### Claude Code

```text
/plugin marketplace add haakond/aws-cost-calculator-skill
/plugin install aws-cost-calculator@aws-cost-calculator
```

Or in one command (Claude Code 2.1.275 or later):

```text
/plugin install aws-cost-calculator --marketplace haakond/aws-cost-calculator-skill
```

Choose a scope when prompted, then run `/reload-plugins` if asked. The skill activates when a request is about an AWS cost estimate; it can also be run as `/aws-cost-calculator:aws-cost-calculator`. Verify with `claude plugin list`.

### Kiro

Install as a [Kiro Power](https://kiro.dev/docs/powers/): Powers panel → **Add Custom Power** → **Import power from GitHub** → `https://github.com/haakond/aws-cost-calculator-skill` → **Install**.

For a local clone, choose **Import power from a folder** and select the clone's root directory (the one containing `plugin.json`).

The Power activates when a request mentions one of the keywords in `plugin.json` (`aws`, `pricing`, `cost`, `estimate`, ...).

Do not also copy the skill into `~/.kiro/skills/`; the skill would be registered twice.

### Cursor

Import the repository as a plugin: **Customize** → **Add Marketplace** → **Import from Repo** → `https://github.com/haakond/aws-cost-calculator-skill`. Cursor reads the root `plugin.json` ([Agent Plugins format](https://cursor.com/docs/plugins)), which brings in the skill and both MCP servers.

If the import is unavailable in the installed Cursor version, install the pieces manually:

1. MCP servers, one click each: [calculator server](https://cursor.com/en/install-mcp?name=aws-pricing-calculator-mcp-server&config=eyJjb21tYW5kIjoibnB4IiwiYXJncyI6WyIteSIsInNhbXBsZS1hd3MtcHJpY2luZy1jYWxjdWxhdG9yLW1jcEBsYXRlc3QiXX0%3D) and [AWS Knowledge server](https://cursor.com/en/install-mcp?name=aws-knowledge-mcp-server&config=eyJ1cmwiOiJodHRwczovL2tub3dsZWRnZS1tY3AuZ2xvYmFsLmFwaS5hd3MifQ%3D%3D), or add the JSON from [`mcp.json`](mcp.json) to `~/.cursor/mcp.json`.
2. Skill: copy `skills/aws-cost-calculator/` to `~/.cursor/skills/` (Cursor also reads `~/.claude/skills/` and `~/.agents/skills/`).

### Other agents

GitHub Copilot, Gemini CLI and any other client that supports Agent Skills and MCP can use the skill in two manual steps.

1. Register both servers using the JSON in [`mcp.json`](mcp.json). In Claude Code without the plugin:

   ```sh
   claude mcp add aws-pricing-calculator-mcp-server -- npx -y sample-aws-pricing-calculator-mcp@latest
   claude mcp add --transport http aws-knowledge-mcp-server https://knowledge-mcp.global.api.aws
   ```

   For VS Code / GitHub Copilot use the "Install in VS Code" badge in the [calculator server README](https://github.com/aws-samples/sample-aws-pricing-calculator-mcp), and note that VS Code uses a `servers` key instead of `mcpServers`.

2. Copy `skills/aws-cost-calculator/` into the agent's skills directory:

   | Agent | Personal | Project |
   |---|---|---|
   | GitHub Copilot | `~/.copilot/skills/` (also reads `~/.claude/skills/`, `~/.agents/skills/`) | `.github/skills/` (also reads `.claude/skills/`, `.agents/skills/`) |
   | Gemini CLI | `~/.gemini/skills/` (or `~/.agents/skills/`) | `.gemini/skills/` (or `.agents/skills/`) |
   | Claude Code (without the plugin) | `~/.claude/skills/` | `.claude/skills/` |

Restart the client afterwards: MCP servers and skills are not picked up by a running session. To verify, ask the agent to call `get_server_info` (calculator server) and to search the AWS documentation (Knowledge server).

## Repository contents

| Path | Used by |
|---|---|
| `skills/aws-cost-calculator/SKILL.md` | The skill itself ([Agent Skills specification](https://agentskills.io/specification)); every route above |
| `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.mcp.json` | Claude Code plugin and marketplace |
| `plugin.json`, `mcp.json` | Agent Plugins format: Kiro Power, Cursor plugin import |
| `scripts/check_manifests.py`, `.github/workflows/validate.yml` | CI checks |
| `.pre-commit-config.yaml`, `scripts/check-commit-msg-trailers.sh` | Local commit-msg hook |

Tool names in the skill are written as bare MCP tool names (`create_estimate`, `add_service`); each client adds its own prefix. Install steps and directory locations follow each vendor's documentation as of October 2026 and should be re-checked if a client changes. The behaviours `SKILL.md` describes as "confirmed live" (duplicate rows on re-add, group overwrite on repeated `add_service` calls) were observed against the calculator server at the time of writing and may have changed.

## Development

GitHub Actions (`.github/workflows/validate.yml`) validates the skill with the Agent Skills reference validator (`skills-ref`, pinned to a commit) and runs `scripts/check_manifests.py`, which checks that the plugin manifests, both MCP server files and `SKILL.md` agree on name, version, license and the required servers. Bump the version in `plugin.json`, `.claude-plugin/plugin.json` and the `SKILL.md` frontmatter together. Run `claude plugin validate .` locally before releasing; it is not part of CI.

After cloning, install the git hooks with `pre-commit install --hook-type pre-commit --hook-type commit-msg`. Plain `pre-commit install` skips the `commit-msg` hook, which rejects co-author and assistant-attribution trailers.

## License

[MIT](LICENSE.md)
