---
name: aws-pricing-calculator-getting-started
description: Onboarding for the aws-pricing-calculator plugin or Kiro Power. Use when the user has just installed it, asks what it does or how to get started, or wants to check that its two MCP servers are connected. For building an actual estimate, use the aws-pricing-calculator skill.
license: MIT
metadata:
  author: Håkon Eriksen Drange
  version: "0.1.0"
---

# Getting started with AWS Pricing Calculator

## Overview

This plugin turns Terraform, other Infrastructure as Code, design documents or a list of services into a shareable AWS Pricing Calculator (`calculator.aws`) estimate. It contains two skills and two MCP servers:

| Component | Role |
|---|---|
| `aws-pricing-calculator` skill | The estimating workflow: inventory, documentation check, basis file, confirmation, build, link |
| `aws-pricing-calculator-getting-started` skill | This onboarding guide |
| `pricing-calculator` MCP server | Builds the estimate on `calculator.aws` and returns the share link (required, needs Node.js) |
| `aws-knowledge` MCP server | Checks the design against current AWS documentation (strongly recommended) |

Neither server needs AWS credentials.

## Prerequisites checklist

- [ ] Node.js is installed (the `pricing-calculator` server starts with `npx`)
- [ ] The `pricing-calculator` server is connected: its `get_server_info` tool is available in this session
- [ ] The `aws-knowledge` server is connected: its documentation search tool is available in this session

## Step-by-step guide

### 1. Check the servers

Call `get_server_info` on the `pricing-calculator` server and report its version. Then run one small documentation search on the `aws-knowledge` server, for example "Amazon S3 pricing". Report which servers are connected. Do not create or change any estimate during onboarding.

### 2. Explain the workflow

Summarize what happens when the user asks for an estimate:

1. The agent lists the AWS services from the material provided and asks for usage figures it cannot find.
2. It checks the design against AWS documentation for costs the calculator does not model.
3. It writes a basis file, `cost-estimate/<name>.md`, with sources, plan, assumptions and findings.
4. It shows a plan table and waits for approval. Nothing is written to `calculator.aws` before that.
5. It builds and validates the estimate and returns the `calculator.aws` link.
6. It updates the basis file with the link and a history row. The user commits the file.

### 3. Ask what to estimate

Ask the user for:

- The source: a Terraform directory, plan output, a design document, or a list of services
- The AWS Region
- Any usage figures already known (requests per second, data volume, storage, run hours)

Then hand over to the `aws-pricing-calculator` skill.

## Example prompts

```text
Analyze the Terraform in ./infra and produce an AWS Pricing Calculator estimate for eu-west-1.
Read docs/solution-design.md and estimate the monthly cost of the proposed architecture.
Estimate an S3 bucket with 500 GB of images behind CloudFront, mostly EU traffic.
```

## Troubleshooting

### `pricing-calculator` is not connected
**Solution:** Check that `node --version` works in a terminal, then restart the client or reload the plugin. MCP servers are only picked up at session start.

### `aws-knowledge` is not connected or rate-limited
**Solution:** The estimate can still be built, but the documentation check is skipped and the basis file says so. Retry later or continue without it.

### A tool exists but calls fail
**Solution:** The `pricing-calculator` server is an AWS sample that uses undocumented calculator APIs, which can change. Report the error text to the user rather than retrying with different inputs.
