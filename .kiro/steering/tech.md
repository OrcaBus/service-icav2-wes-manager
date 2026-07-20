# Tech Stack

## Languages

- **TypeScript** — Infrastructure as Code (AWS CDK), build tooling, tests
- **Python 3.14** — All Lambda functions and the REST API interface

## Infrastructure

- **AWS CDK** (v2.258+) with `aws-cdk-lib`
- **@orcabus/platform-cdk-constructs** (v1.7.2) — shared OrcaBus CDK constructs (DeploymentStackPipeline, PythonUvFunction, API Gateway config, shared constants)
- **@aws-cdk/aws-lambda-python-alpha** — Python Lambda bundling
- **cdk-nag** — compliance/security checks
- **sqs-dlq-monitoring** — DLQ alerting construct

## AWS Services

Lambda, Step Functions (ASL JSON), DynamoDB, S3, SQS, EventBridge, ECS Fargate, API Gateway (HTTP), Secrets Manager, SSM Parameter Store, CodePipeline

## Python Libraries (Lambdas / API)

- **FastAPI** + **Mangum** — REST API served via Lambda behind API Gateway
- **Pydantic** v2 — request/response validation
- **dyntastic** — DynamoDB ORM
- **aws-durable-execution-sdk-python** — durable Lambda execution with wait-for-callback patterns
- **boto3** — AWS SDK
- **orcabus_api_tools** — shared OrcaBus API toolkit (provided as Lambda layer)
- ICAv2 toolkit layer — ICAv2 API integration (provided as Lambda layer)

## Build & Package Management

- **pnpm** (v11.1.3) — Node.js package manager (corepack-managed)
- **Makefile** — top-level task runner
- **ts-node** — CDK synthesis
- **Jest** + ts-jest — CDK/infrastructure tests

## Code Quality

- **ESLint** (v10) + typescript-eslint — TypeScript linting
- **Prettier** — formatting (single quotes, 100 char width, 2-space indent, trailing commas)
- **pre-commit** — git hooks (secrets detection, large file checks, YAML validation, eslint, prettier)
- **detect-secrets** — prevents committing secrets

## Common Commands

```bash
# Install dependencies
make install          # or: pnpm install --frozen-lockfile

# Run all checks (audit, prettier, eslint, pre-commit)
make check

# Auto-fix formatting and lint issues
make fix

# Run tests (TypeScript compile + Jest)
make test

# CDK synthesis
pnpm cdk-stateless synth
pnpm cdk-stateful synth

# CDK deploy (example)
pnpm cdk-stateless deploy <stack-name>

# List available stacks
pnpm cdk-stateless ls
pnpm cdk-stateful ls

# Formatting only
pnpm prettier         # check
pnpm prettier-fix     # fix

# Linting only
pnpm lint             # check
pnpm lint-fix         # fix
```

## TypeScript Configuration

- Target: ES2020
- Module: CommonJS
- Strict mode enabled
- No emit (type-checking only, ts-node for execution)

## Prettier Rules

- Print width: 100
- Single quotes, trailing commas (es5)
- 2-space indent, no tabs
- Arrow parens: always
- Bracket spacing: true
