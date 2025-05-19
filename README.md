# Service ICAv2 WES Manager

## Overview

Submit jobs / events via the WES API.
We'll handle the rest of the 'icav2' drama for you!

### Events Overview

Essentially we hanlde ICAv2 requests on an internal event bus
but retrieve requests from the external event bus for the WES API.

We also send back 'important' state change events to the external event bus.

ICAv2 state change events comprise the following list of statuses:

* REQUESTED
* QUEUED
* INITIALIZING
* PREPARING_INPUTS
* IN_PROGRESS
* GENERATING_OUTPUTS
* AWAITING_INPUT
* ABORTING
* SUCCEEDED
* FAILED
* FAILED_FINAL
* ABORTED

This is a lot and floods our external event bus.
We trim this down to the following statuses for the WES API:

* QUEUED
* IN_PROGRESS (renamed to RUNNING)
* SUCCEEDED
* FAILED
* ABORTED

![Events Overview](./docs/drawio-exports/icav2-wes-handler-events.drawio.svg)

### WES API Overview

We support the following endpoints

**GET**

* api/v1/analyses/
* api/v1/analyses/{id}/

**POST**

* api/v1/analyses/

**PATCH**

* api/v1/analyses/{id}:abort

### WES POST

The WES POST endpoint is used to submit a new analysis job.

The request body should contain the following keys:

* **name**: The unique name of the analysis job,
  * this will be mapped to the user-reference attribute.

* **inputs**:
  * A key-value store of inputs.
  * For CWL based workflows this will look like a standard CWL inputs object
  * For nextflow based workflows, we assume URIs are provided for file / directory parameters

* **tags**:
  * A key-value store of tags.
  * These will be added to the analysis jobs as user-defined tags

* **engineParameters**:
  * projectId - the ICAv2 project context to run the analysis in
  * pipelineId - the ICAv2 pipeline id to run
  * outputUri - the output location to store the results of the analysis
  * logsUri - the location to store the logs of the analysis (only available after the project has completed)

:construction:

In future we will support the following keys in the engineParameters object:
  * queue: Enum - The queue to run the analysis in,
    analyses are then not submitted to the ICAv2 API until a slot in the queue is available.
  * priority: int - The priority of the analysis,
    this is a number between 1 and 10, with 10 being the highest priority.
  * preBundle: boolean - Whether to pre-bundle the analysis or not,
    this is a boolean value, with true being pre-bundled and false being not pre-bundled.
    Useful for if input data is not readily available in the project analysis context.
    After the analysis is completed, bundles are unlinked from the project and deprecated.
  * Validate Schema - Whether to pull in the JSON Schema from the workflow first and validate the inputs
    against the JSON schema before submitting the analysis job to ICAv2.'
  * Pipeline endpoint, push a pipeline in 'ZIP' format. This might be from nf-core or a CWL pipeline.
    The pipeline can then be run via the WES API.
    The pipeline endpoint will handle the 'icav2-drama' for you, for nextflow pipelines specifically,
    this means adding in the icav2 config type. And for both CWL / nextflow pipelines, will generate
    the correct input schema meaning the pipeline can be run both in the UI and API.

<details>

<summary>Click to expand</summary>

```json5
{
  "name": "my-analysis-job",
  "inputs": {
    "my-sample": {
      "class": "File",
      "location": "s3://my-bucket/my-sample.bam"
    },
    "my-boolean-parameter": False,
    "my-string-parameter": "my-string-value"
  },
  "tags": {
    "libraryId": "L1234567"
  },
  "engineParameters": {
    "projectId": "abcd-1234-efgh-5678-ijklmnop",  // pragma: allowlist secret
    "pipelineId": "P1234567",
    "outputUri": "s3://my-bucket/my-analysis-job-output/",
    "logsUri": "s3://my-bucket/my-analysis-job-logs/"
  }
}
```

</details>


### WES GET

Get requests contain the same information as a POST request but with the following additional keys.

* id:  The ICAv2 WES Handler Orcabus Id
* status: The status of the analysis job
* submissionTime: The time the analysis job was submitted to the WES API
* startTime: The time the analysis job started running on ICAv2
* endTime: The time the analysis job finished running on ICAv2
* errorMessage: The error message if the analysis job failed

> To keep compatibility with both CWL AND Nextflow, we do not use output jsons as available in CWL,
> instead we expect all data and metadata to be available in the analysis job output location.

## Step Functions Overview

### Submit job to ICA

This will become more complex as we add queueing and priority support to the WES API.

Along with JSON-schema validation steps and pre-bundling support.

![Submit job to ICA](./docs/workflow-studio-exports/launch-icav2-analysis-sfn.svg)

### Retrieve ICAv2 Analysis State Change Event

This step function is triggered by an ICAv2 analysis state change event.

![Retrieve ICAv2 Analysis State Change Event](./docs/workflow-studio-exports/handle-icav2-state-change-event-sfn.svg)

### Abort ICAv2 Analysis

Handles an abort request from the WES API.

While this step function is just a simple lambda, by placing in an SFN like this, we can
set retries to 60 seconds and a max of 5 attempts.

![Abort ICAv2 Analysis](./docs/workflow-studio-exports/abort-analysis-sfn.svg)

:construction: EVERYTHING BELOW HERE :construction:

## Project Structure

The project is organized into the following key directories:

- **`./app`**: Contains the main application logic. You can open the code editor directly in this folder, and the application should run independently.

- **`./bin/deploy.ts`**: Serves as the entry point of the application. It initializes two root stacks: `stateless` and `stateful`. You can remove one of these if your service does not require it.

- **`./infrastructure`**: Contains the infrastructure code for the project:
  - **`./infrastructure/toolchain`**: Includes stacks for the stateless and stateful resources deployed in the toolchain account. These stacks primarily set up the CodePipeline for cross-environment deployments.
  - **`./infrastructure/stage`**: Defines the stage stacks for different environments:
    - **`./infrastructure/stage/config.ts`**: Contains environment-specific configuration files (e.g., `beta`, `gamma`, `prod`).
    - **`./infrastructure/stage/stack.ts`**: The CDK stack entry point for provisioning resources required by the application in `./app`.

- **`.github/workflows/pr-tests.yml`**: Configures GitHub Actions to run tests for `make check` (linting and code style), tests defined in `./test`, and `make test` for the `./app` directory. Modify this file as needed to ensure the tests are properly configured for your environment.

- **`./test`**: Contains tests for CDK code compliance against `cdk-nag`. You should modify these test files to match the resources defined in the `./infrastructure` folder.

## Setup

### Requirements

```sh
node --version
v22.9.0

# Update Corepack (if necessary, as per pnpm documentation)
npm install --global corepack@latest

# Enable Corepack to use pnpm
corepack enable pnpm

```

### Install Dependencies

To install all required dependencies, run:

```sh
make install
```

### CDK Commands

You can access CDK commands using the `pnpm` wrapper script.

This template provides two types of CDK entry points: `cdk-stateless` and `cdk-stateful`.

- **`cdk-stateless`**: Used to deploy stacks containing stateless resources (e.g., AWS Lambda), which can be easily redeployed without side effects.
- **`cdk-stateful`**: Used to deploy stacks containing stateful resources (e.g., AWS DynamoDB, AWS RDS), where redeployment may not be ideal due to potential side effects.

The type of stack to deploy is determined by the context set in the `./bin/deploy.ts` file. This ensures the correct stack is executed based on the provided context.

For example:

```sh
# Deploy a stateless stack
pnpm cdk-stateless <command>

# Deploy a stateful stack
pnpm cdk-stateful <command>
```

### Stacks

This CDK project manages multiple stacks. The root stack (the only one that does not include `DeploymentPipeline` in its stack ID) is deployed in the toolchain account and sets up a CodePipeline for cross-environment deployments to `beta`, `gamma`, and `prod`.

To list all available stacks, run:

```sh
pnpm cdk-stateless ls
```

Example output:

```sh
OrcaBusStatelessServiceStack
OrcaBusStatelessServiceStack/DeploymentPipeline/OrcaBusBeta/DeployStack (OrcaBusBeta-DeployStack)
OrcaBusStatelessServiceStack/DeploymentPipeline/OrcaBusGamma/DeployStack (OrcaBusGamma-DeployStack)
OrcaBusStatelessServiceStack/DeploymentPipeline/OrcaBusProd/DeployStack (OrcaBusProd-DeployStack)
```

## Linting and Formatting

### Run Checks

To run linting and formatting checks on the root project, use:

```sh
make check
```

### Fix Issues

To automatically fix issues with ESLint and Prettier, run:

```sh
make fix
```
