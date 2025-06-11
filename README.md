# Service ICAv2 WES Manager

## Overview

Submit jobs / events via the WES API.
We'll handle the rest of the 'icav2' drama for you!

## Events Overview

Essentially we handle ICAv2 requests on an internal event bus
but retrieve requests from the external event bus for the WES API.

We also send back 'important' state change events to the external event bus.

### Status Enum

ICAv2 state change events comprise the following list of statuses:

<details>

<summary>Click to expand</summary>

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

</details>

This is a lot and floods our external event bus.
We trim this down and map these to the equivalent states in [AWS BATCH](https://docs.aws.amazon.com/batch/latest/APIReference/API_JobDetail.html)
Although we keep the 'ABORTED' status as is.

<details>

<summary>Click to expand</summary>

* SUBMITTED: On post request from the WES API
* PENDING: In the WES API Queue (:construction: Not yet implemented, will be added in the future when we add in the queue system)
* RUNNABLE: Step Function to run the analysis has been triggered.
* STARTING: Event from ICAv2 parsed through, the process has been registered on ICAv2
  * (renamed from INITIALIZING)
* RUNNING (renamed from IN_PROGRESS)
* SUCCEEDED: The analysis has completed successfully.
* FAILED: The analysis has failed.
* ABORTED: The analysis has been aborted.

</details>

![Events Overview](./docs/drawio-exports/icav2-wes-handler-events.drawio.svg)

### WES State Change Requests

<details>

<summary>Click to expand!</summary>

```json5
{
  "DetailType": "Icav2WesAnalysisStateChange",
  "source": "orcabus.icav2wesmanager",
  "account": "843407916570",
  "time": "2025-05-28T03:54:35Z",
  "region": "ap-southeast-2",
  "resources": [],
  "detail": {
    "id": "iwa.01JWAGE5PWS5JN48VWNPYSTJRN",
    "name": "bclconvert-interop-qc",
    "inputs": {
      "bclconvert_report_directory": {
        "class": "Directory",
        "location": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/primary/20231010_pi1-07_0329_A222N7LTD3/202504179cac7411/Reports/"
      },
      "interop_directory": {
        "class": "Directory",
        "location": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/primary/20231010_pi1-07_0329_A222N7LTD3/202504179cac7411/InterOp/"
      },
      "instrument_run_id": "20231010_pi1-07_0329_A222N7LTD3"
    },
    "engineParameters": {
      "pipelineId": "55a8bb47-d32b-48dd-9eac-373fd487ccec",
      "projectId": "ea19a3f5-ec7c-4940-a474-c31cd91dbad4",
      "outputUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/test_data/bclconvert-interop-qc-test/",
      "logsUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/test_data/logs/bclconvert-interop-qc-test/"
    },
    "tags": {
      "instrument_run_id": "20231010_pi1-07_0329_A222N7LTD3"
    },
    "status": "SUBMITTED",
    "submissionTime": "2025-05-28T03:54:35.612655",
    "stepsLaunchExecutionArn": "arn:aws:states:ap-southeast-2:843407916570:execution:icav2-wes-launchIcav2Analysis:3f176fc2-d8e0-4bd5-8d2f-f625d16f6bf6",
    "icav2AnalysisId": null,
    "startTime": "2025-05-28T03:54:35.662401+00:00",
    "endTime": null
  }
}
```

Once an analysis has launched on ICAv2, we will forward sqs events in the ICAv2 WES analysis status changes enum list.

We will also populate the analysis id in the `icav2AnalysisId` field once the analysis has been launched on ICAv2.

</details>

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
  * These will be added to the analysis jobs as user tags

* **engineParameters**:
  * projectId - the ICAv2 project context to run the analysis in
  * pipelineId - the ICAv2 pipeline id to run
  * outputUri - the output location to store the results of the analysis
  * logsUri - the location to store the logs of the analysis (only available after the project has completed)


<details>

<summary>Click to expand</summary>

```json5
 {
  // The unique analysis name
  "name": "bclconvert-interop-qc",
  // The inputs to the analysis
  "inputs": {
    "bclconvert_report_directory": {
      "class": "Directory",
      "location": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/primary/20231010_pi1-07_0329_A222N7LTD3/202504179cac7411/Reports/"
    },
    "interop_directory": {
      "class": "Directory",
      "location": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/primary/20231010_pi1-07_0329_A222N7LTD3/202504179cac7411/InterOp/"
    },
    "instrument_run_id": "20231010_pi1-07_0329_A222N7LTD3"
  },
  // The engine parameters for the analysis
  "engineParameters": {
    // The ICAv2 pipeline id to run
    "pipelineId": "55a8bb47-d32b-48dd-9eac-373fd487ccec",
    // The ICAv2 project id to run the analysis in
    "projectId": "ea19a3f5-ec7c-4940-a474-c31cd91dbad4",
    // The output location to store the results of the analysis
    "outputUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/test_data/bclconvert-interop-qc-test/",
    // The location to store the logs of the analysis
    "logsUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/test_data/logs/bclconvert-interop-qc-test/"
  },
  // Any tags to add to the analysis job (helpful for finding the analysis job later)
  "tags": {
    "instrument_run_id": "20231010_pi1-07_0329_A222N7LTD3"
  },
  "status": "SUBMITTED"
}
```

</details>

To run this over the WES API, you can use the following curl command:

```bash
curl \
  --silent --show-error --location --fail \
  --request "POST" \
  --header "Accept: application/json" \
  --header "Authorization: Bearer ${ORCABUS_TOKEN}" \
  --header "Content-Type: application/json" \
  --data "$( \
    jq --raw-output \
      '
        {
          "name": "bclconvert-interop-qc--20231010_pi1-07_0329_A222N7LTD3",
          "inputs": {
            "bclconvert_report_directory": {
              "class": "Directory",
              "location": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/primary/20231010_pi1-07_0329_A222N7LTD3/202504179cac7411/Reports/"
            },
            "interop_directory": {
              "class": "Directory",
              "location": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/primary/20231010_pi1-07_0329_A222N7LTD3/202504179cac7411/InterOp/"
            },
            "instrument_run_id": "20231010_pi1-07_0329_A222N7LTD3"
          },
          "engineParameters": {
            "pipelineId": "55a8bb47-d32b-48dd-9eac-373fd487ccec",
            "projectId": "ea19a3f5-ec7c-4940-a474-c31cd91dbad4",
            "outputUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/test_data/bclconvert-interop-qc-test/",
            "logsUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/test_data/logs/bclconvert-interop-qc-test/"
          },
          "tags": {
            "instrument_run_id": "20231010_pi1-07_0329_A222N7LTD3"
          }
        }
      ' \
  )" \
  --url "https://icav2-wes.dev.umccr.org/api/v1/analysis/"
```

You can also use an event bus to submit the analysis job, which will be handled by the WES API.

```json5
{
  "EventBusName": "OrcaBusMain",
  "DetailType": "Icav2WesAnalysisRequest",
  "Source": "your source",
  "Detail": {
    // The same as the POST request body above as a json body
  }
}
```


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

You can retrieve the analysis job by name or id.

You can also retrieve all analyses jobs by using the `GET /api/v1/analyses/` endpoint.

#### By Name

<details>

<summary>Click to expand</summary>

```bash
curl \
  --silent --show-error --location --fail \
  --request "GET" \
  --header "Accept: application/json" \
  --header "Authorization: Bearer ${ORCABUS_TOKEN}" \
  --url "https://icav2-wes.dev.umccr.org/api/v1/analysis?name=bclconvert-interop-qc--20231010_pi1-07_0329_A222N7LTD3"
```

Will retrieve the following response in pagination format

```json
{
  "links": {
    "previous": null,
    "next": null
  },
  "pagination": {
    "page": 1,
    "rowsPerPage": 100,
    "count": 1
  },
  "results": [
    {
      "id": "iwa.01JWAGE5PWS5JN48VWNPYSTJRN",
      "name": "bclconvert-interop-qc--20231010_pi1-07_0329_A222N7LTD3",
      "inputs": {
        "bclconvert_report_directory": {
          "class": "Directory",
          "location": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/primary/20231010_pi1-07_0329_A222N7LTD3/202504179cac7411/Reports/"
        },
        "instrument_run_id": "20231010_pi1-07_0329_A222N7LTD3",
        "interop_directory": {
          "class": "Directory",
          "location": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/primary/20231010_pi1-07_0329_A222N7LTD3/202504179cac7411/InterOp/"
        }
      },
      "engineParameters": {
        "pipelineId": "55a8bb47-d32b-48dd-9eac-373fd487ccec",
        "projectId": "ea19a3f5-ec7c-4940-a474-c31cd91dbad4",
        "outputUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/test_data/bclconvert-interop-qc-test/",
        "logsUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/test_data/logs/bclconvert-interop-qc-test/"
      },
      "tags": {
        "instrument_run_id": "20231010_pi1-07_0329_A222N7LTD3"
      },
      "status": "SUCCEEDED",
      "submissionTime": "2025-05-28T03:54:35.612655",
      "stepsLaunchExecutionArn": "arn:aws:states:ap-southeast-2:843407916570:execution:icav2-wes-launchIcav2Analysis:3f176fc2-d8e0-4bd5-8d2f-f625d16f6bf6",
      "icav2AnalysisId": "b7157552-74a1-4ff4-a6b3-b37a85a485cf",
      "startTime": "2025-05-28T03:54:35.662401Z",
      "endTime": "2025-05-28T04:32:26.456422Z"
    }
  ]
}
```

</details>

#### By Id

Alternatively, you can retrieve the analysis job by id by appending the id to the endpoint.

<details>

<summary>Click to expand!</summary>

```shell
curl \
  --silent --show-error --location --fail \
  --request "GET" \
  --header "Accept: application/json" \
  --header "Authorization: Bearer ${ORCABUS_TOKEN}" \
  --url "https://icav2-wes.dev.umccr.org/api/v1/analysis/iwa.01JWAGE5PWS5JN48VWNPYSTJRN"
```

Which will return the same response as above, but without the pagination links.

```json
{
  "id": "iwa.01JWAGE5PWS5JN48VWNPYSTJRN",
  "name": "bclconvert-interop-qc--20231010_pi1-07_0329_A222N7LTD3",
  "inputs": {
    "bclconvert_report_directory": {
      "class": "Directory",
      "location": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/primary/20231010_pi1-07_0329_A222N7LTD3/202504179cac7411/Reports/"
    },
    "instrument_run_id": "20231010_pi1-07_0329_A222N7LTD3",
    "interop_directory": {
      "class": "Directory",
      "location": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/primary/20231010_pi1-07_0329_A222N7LTD3/202504179cac7411/InterOp/"
    }
  },
  "engineParameters": {
    "pipelineId": "55a8bb47-d32b-48dd-9eac-373fd487ccec",
    "projectId": "ea19a3f5-ec7c-4940-a474-c31cd91dbad4",
    "outputUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/test_data/bclconvert-interop-qc-test/",
    "logsUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/test_data/logs/bclconvert-interop-qc-test/"
  },
  "tags": {
    "instrument_run_id": "20231010_pi1-07_0329_A222N7LTD3"
  },
  "status": "SUCCEEDED",
  "submissionTime": "2025-05-28T03:54:35.612655",
  "stepsLaunchExecutionArn": "arn:aws:states:ap-southeast-2:843407916570:execution:icav2-wes-launchIcav2Analysis:3f176fc2-d8e0-4bd5-8d2f-f625d16f6bf6",
  "icav2AnalysisId": "b7157552-74a1-4ff4-a6b3-b37a85a485cf",
  "startTime": "2025-05-28T03:54:35.662401Z",
  "endTime": "2025-05-28T04:32:26.456422Z"
}
```

</details>




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
pnpm cdk-stateless deploy OrcaBusStatelessICAv2WesStack/Icav2WesManagerStatelessDeploymentPipeline/OrcaBusBeta/Icav2WesManagerStatelessDeployStack

# Deploy a stateful stack
pnpm cdk-stateful deploy OrcabusStatefulICAv2WesStack/Icav2WesManagerStatefulDeployPipeline/OrcaBusBeta/Icav2WesManagerStatefulDeployStack
```

### Stacks

This CDK project manages multiple stacks. The root stack (the only one that does not include `DeploymentPipeline` in its stack ID) is deployed in the toolchain account and sets up a CodePipeline for cross-environment deployments to `beta`, `gamma`, and `prod`.

To list all available stacks, run:

```sh
pnpm cdk-stateless ls
```

Example output:

```sh
OrcaBusStatelessICAv2WesStack
OrcaBusStatelessICAv2WesStack/DeploymentPipeline/OrcaBusBeta/DeployStack (OrcaBusBeta-DeployStack)
OrcaBusStatelessICAv2WesStack/DeploymentPipeline/OrcaBusGamma/DeployStack (OrcaBusGamma-DeployStack)
OrcaBusStatelessICAv2WesStack/DeploymentPipeline/OrcaBusProd/DeployStack (OrcaBusProd-DeployStack)
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

## Road map :construction:

#### Scheduling support

Support the following enums

* queue: Enum - The queue to run the analysis in,
  analyses are then not submitted to the ICAv2 API until a slot in the queue is available.
* priority: int - The priority of the analysis,
  this is a number between 1 and 10, with 10 being the highest priority.

#### Data-to-compute support

* preBundle: boolean - Whether to pre-bundle the analysis or not,
  this is a boolean value, with true being pre-bundled and false being not pre-bundled.
  Useful for if input data is not readily available in the project analysis context.
  After the analysis is completed, bundles are unlinked from the project and deprecated.

We also may look at storage Credentials options, in a later release of wrapica.

#### JSON Schema validation support

* Validate Schema - Whether to pull in the JSON Schema from the workflow first and validate the inputs
  against the JSON schema before submitting the analysis job to ICAv2.'

#### Pipeline endpoint support

* Pipeline endpoint, push a pipeline in 'ZIP' format. This might be from nf-core or a CWL pipeline.
  The pipeline can then be run via the WES API.
  The pipeline endpoint will handle the 'icav2-drama' for you, for nextflow pipelines specifically,
  this means adding in the icav2 config type. And for both CWL / nextflow pipelines, will generate
  the correct input schema meaning the pipeline can be run both in the UI and API.
