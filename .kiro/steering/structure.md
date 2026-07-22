# Project Structure

## Top-Level Layout

```
├── app/                           # Application logic (Python)
├── bin/deploy.ts                  # CDK app entry point
├── infrastructure/                # CDK infrastructure code (TypeScript)
├── test/                          # CDK nag compliance tests
├── docs/                          # Diagrams (drawio, workflow studio SVGs)
├── scratch/                       # Scratch/experimental files
├── Makefile                       # Top-level task runner
├── package.json                   # Node dependencies and scripts
└── tsconfig.json                  # TypeScript config
```

## app/ — Application Code (Python)

```
app/
├── ecs/                           # ECS Fargate container definitions
│   ├── validate_bam_file/         # BAM file validation container
│   └── validate_vcf_file/         # VCF file validation container
├── event-schemas/                 # JSON schemas for EventBridge events
├── interface/                     # FastAPI REST API
│   ├── handler.py                 # Mangum entry point
│   ├── requirements.txt           # API Python dependencies
│   └── icav2_wes_api/             # API package (routes, models, events, utils)
├── lambdas/                       # Lambda functions (one folder per lambda)
│   ├── {snake_case_name}_py/      # Each lambda folder
│   │   ├── {snake_case_name}.py   # Handler (exports `handler`)
│   │   └── requirements.txt       # Optional per-lambda deps
│   └── ...
└── step-functions-templates/      # ASL JSON state machine definitions
    └── {snake_case_name}_sfn_template.asl.json
```

### Lambda Naming Convention

Lambda names are defined in camelCase in TypeScript (`generateWesPostRequestFromEvent`) and auto-converted to snake_case for file paths (`generate_wes_post_request_from_event_py/generate_wes_post_request_from_event.py`).

## infrastructure/ — CDK Code (TypeScript)

```
infrastructure/
├── stage/                         # Environment-specific constructs
│   ├── api/                       # API Gateway setup
│   ├── dynamodb/                  # DynamoDB table definitions
│   ├── ecs/                       # ECS Fargate task constructs
│   ├── event-rules/               # EventBridge rule constructs
│   ├── event-schemas/             # Schema registry constructs
│   ├── event-targets/             # EventBridge target constructs
│   ├── lambda/                    # Lambda builder (interfaces, index)
│   ├── s3/                        # S3 bucket constructs
│   ├── sqs/                       # SQS queue constructs
│   ├── step-functions/            # Step Function builder (interfaces, index)
│   ├── utils/                     # Helpers (camelCase↔snake_case)
│   ├── config.ts                  # Per-environment config (BETA/GAMMA/PROD)
│   ├── constants.ts               # All shared constants
│   ├── interfaces.ts              # Stack configuration interfaces
│   ├── stateful-application-stack.ts   # Stateful resources (DynamoDB, S3, SQS, EventBridge)
│   └── stateless-application-stack.ts  # Stateless resources (Lambda, SFN, API, ECS)
└── toolchain/                     # CI/CD pipeline stacks
    ├── constants.ts               # Repo name etc.
    ├── stateful-stack.ts          # Stateful CodePipeline
    └── stateless-stack.ts         # Stateless CodePipeline
```

## Key Architectural Patterns

- **Stateful/Stateless separation** — Two independent CDK stacks and deployment pipelines, selected via `deployMode` context flag
- **Multi-environment** — BETA, GAMMA, PROD configs with CodePipeline cross-account deployment
- **Builder pattern** — Each resource type has a `buildAll*()` function composed in the application stack
- **Requirements maps** — Declarative permission/config maps (`lambdaToRequirementsMap`, `sfnToRequirementsMap`) control what each Lambda/SFN needs
- **Convention-based wiring** — camelCase names drive folder paths, file names, and CDK resource IDs automatically
- **ASL JSON templates** — Step Functions use JSON definitions with `__placeholder__` substitution for ARNs
- **Durable execution** — Key Lambdas use `@durable_execution` with `wait_for_callback` for long-running async workflows
- **Lambda layers** — Shared code (ICAv2 toolkit, OrcaBus API tools) packaged as layers, not inline
