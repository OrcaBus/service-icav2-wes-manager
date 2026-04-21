// Imports
import * as sfn from 'aws-cdk-lib/aws-stepfunctions';
import { Construct } from 'constructs';
import * as path from 'path';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as cdk from 'aws-cdk-lib';

// Local interfaces
import {
  BuildSfnsProps,
  sfnNameList,
  SfnObjectProps,
  SfnProps,
  sfnToRequirementsMap,
  stepFunctionEcsMap,
  stepFunctionToLambdaMap,
} from './interfaces';
import { camelCaseToSnakeCase } from '../utils';
import { STACK_PREFIX, STEP_FUNCTIONS_DIR } from '../constants';
import { NagSuppressions } from 'cdk-nag';
import { LambdaObject } from '../lambda/interfaces';
import { EcsTaskName } from '../ecs/interfaces';

/** Step Function stuff */
function createStateMachineDefinitionSubstitutions(props: SfnProps): {
  [key: string]: string;
} {
  const definitionSubstitutions: { [key: string]: string } = {};

  const sfnRequirements = sfnToRequirementsMap[props.stateMachineName];
  const lambdaFunctionNamesInSfn = stepFunctionToLambdaMap[props.stateMachineName];
  const lambdaFunctions = props.lambdaFunctions.filter((lambdaObject) =>
    lambdaFunctionNamesInSfn.includes(lambdaObject.lambdaName)
  );
  const ecsContainerNamesInSfn = stepFunctionEcsMap[props.stateMachineName];
  const ecsTaskObjects = props.ecsTaskObjects.filter((ecsTaskObject) =>
    ecsContainerNamesInSfn.includes(
      <EcsTaskName>ecsTaskObject.ecsFargateTaskConstruct.containerDefinition.containerName
    )
  );

  /* Substitute lambdas in the state machine definition */
  for (const lambdaObject of lambdaFunctions) {
    const sfnSubtitutionKey = `__${camelCaseToSnakeCase(lambdaObject.lambdaName)}_lambda_function_arn__`;
    definitionSubstitutions[sfnSubtitutionKey] =
      lambdaObject.lambdaFunction.currentVersion.functionArn;
  }

  /* Miscellaneous */
  definitionSubstitutions['__one_hour_in_seconds__'] = String(3600);

  /* Add in fargate constructs */
  for (const ecsTaskObject of ecsTaskObjects) {
    const ecsContainerNameSnakeCase = camelCaseToSnakeCase(
      ecsTaskObject.ecsFargateTaskConstruct.containerDefinition.containerName
    );
    definitionSubstitutions[`__${ecsContainerNameSnakeCase}_cluster_arn__`] =
      ecsTaskObject.ecsFargateTaskConstruct.cluster.clusterArn;
    definitionSubstitutions[`__${ecsContainerNameSnakeCase}_task_definition_arn__`] =
      ecsTaskObject.ecsFargateTaskConstruct.taskDefinition.taskDefinitionArn;
    definitionSubstitutions[`__${ecsContainerNameSnakeCase}_subnets__`] =
      ecsTaskObject.ecsFargateTaskConstruct.cluster.vpc.privateSubnets
        .map((subnet) => subnet.subnetId)
        .join(',');
    definitionSubstitutions[`__${ecsContainerNameSnakeCase}_security_group__`] =
      ecsTaskObject.ecsFargateTaskConstruct.securityGroup.securityGroupId;
    definitionSubstitutions[`__${ecsContainerNameSnakeCase}_container_name__`] =
      ecsTaskObject.ecsFargateTaskConstruct.containerDefinition.containerName;
  }

  /* Sfn Requirements */
  if (sfnRequirements.needsExternalEventBusPutPermissions) {
    definitionSubstitutions['__external_event_bus_name__'] = props.eventBus.eventBusName;
    definitionSubstitutions['__stack_source__'] = props.eventSource;
  }

  if (sfnRequirements.needsPayloadDbPermissions) {
    definitionSubstitutions['__payloads_table_name__'] = props.payloadsTable.tableName;
  }

  if (sfnRequirements.needsCallbackTablePermissions) {
    definitionSubstitutions['__icav2_wes_request_callback_table_name__'] =
      props.callbackTable.tableName;
  }

  if (sfnRequirements.needsSetVisibilityTimeoutPermissions) {
    definitionSubstitutions['__icav2_wes_analysis_queue_url__'] =
      props.icaExternalSqsQueue.queueUrl;
  }

  if (sfnRequirements.needsNestedSfnStartExecutionPermissions) {
    if (props.stateMachineName == 'handleIcav2AnalysisStateChange') {
      for (const nestedSfnName of sfnNameList) {
        // For each of the active nested sfn functions
        // Add in the definition substitution
        switch (nestedSfnName) {
          case 'handleFilemanager':
          case 'handleNextflowFiles':
          case 'unlockCallbackId': {
            definitionSubstitutions[
              `__${camelCaseToSnakeCase(nestedSfnName)}_state_machine_arn__`
            ] =
              `arn:aws:states:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:stateMachine:${STACK_PREFIX}--${nestedSfnName}`;
            break;
          }
        }
      }
    }
  }

  return definitionSubstitutions;
}

function wireUpStateMachinePermissions(scope: Construct, props: SfnObjectProps): void {
  /* Wire up lambda permissions */
  const sfnRequirements = sfnToRequirementsMap[props.stateMachineName];

  const lambdaFunctionNamesInSfn = stepFunctionToLambdaMap[props.stateMachineName];
  const lambdaFunctions = props.lambdaFunctions.filter((lambdaObject) =>
    lambdaFunctionNamesInSfn.includes(lambdaObject.lambdaName)
  );
  const ecsContainerNamesInSfn = stepFunctionEcsMap[props.stateMachineName];
  const ecsTaskObjects = props.ecsTaskObjects.filter((ecsTaskObject) =>
    ecsContainerNamesInSfn.includes(
      <EcsTaskName>ecsTaskObject.ecsFargateTaskConstruct.containerDefinition.containerName
    )
  );

  if (sfnRequirements.needsExternalEventBusPutPermissions) {
    props.eventBus.grantPutEventsTo(props.stateMachineObj);
  }

  if (sfnRequirements.needsPayloadDbPermissions) {
    props.payloadsTable.grantReadWriteData(props.stateMachineObj);
  }

  if (sfnRequirements.needsCallbackTablePermissions) {
    props.callbackTable.grantReadWriteData(props.stateMachineObj);
  }

  if (sfnRequirements.needsSetVisibilityTimeoutPermissions) {
    props.stateMachineObj.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['sqs:ChangeMessageVisibility'],
        resources: [props.icaExternalSqsQueue.queueArn],
      })
    );
  }

  /* Allow the state machine to invoke the lambda function */
  for (const lambdaObject of lambdaFunctions) {
    lambdaObject.lambdaFunction.grantInvoke(props.stateMachineObj);
  }

  /* Nag Suppressions for express sfns */
  // if (sfnRequirements.isExpressSfn) {
  //   NagSuppressions.addResourceSuppressions(
  //     props.stateMachineObj,
  //     [
  //       {
  //         id: 'AwsSolutions-IAM5',
  //         reason: 'Needs permissions to write to logs',
  //       },
  //     ],
  //     true
  //   );
  // }

  // Grant ECS permissions if needed
  if (sfnRequirements.needsEcsPermissions) {
    // Grant the state machine access to run the ECS tasks
    for (const ecsTaskObject of ecsTaskObjects) {
      ecsTaskObject.ecsFargateTaskConstruct.taskDefinition.grantRun(props.stateMachineObj);
    }
    /* Grant the state machine access to monitor the tasks */
    props.stateMachineObj.addToRolePolicy(
      new iam.PolicyStatement({
        resources: [
          `arn:aws:events:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:rule/StepFunctionsGetEventsForECSTaskRule`,
        ],
        actions: ['events:PutTargets', 'events:PutRule', 'events:DescribeRule'],
      })
    );

    /* Will need cdk nag suppressions for this */
    NagSuppressions.addResourceSuppressions(
      props.stateMachineObj,
      [
        {
          id: 'AwsSolutions-IAM5',
          reason: 'Need ability to put targets and rules for ECS task monitoring',
        },
      ],
      true
    );
  }

  if (sfnRequirements.needsDistributedMapSupport) {
    // Requirement for distributed maps to work
    /* State machine runs a distributed map */
    // Because this steps execution uses a distributed map running an express step function, we
    // have to wire up some extra permissions
    // Grant the state machine's role to execute itself
    // However we cannot just grant permission to the role as this will result in a circular dependency
    // between the state machine and the role
    // Instead we use the workaround here - https://github.com/aws/aws-cdk/issues/28820#issuecomment-1936010520
    const distributedMapPolicy = new iam.Policy(scope, `${props.stateMachineName}-dist-map-role`, {
      document: new iam.PolicyDocument({
        statements: [
          new iam.PolicyStatement({
            resources: [props.stateMachineObj.stateMachineArn],
            actions: ['states:StartExecution'],
          }),
          new iam.PolicyStatement({
            resources: [
              `arn:aws:states:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:execution:${props.stateMachineObj.stateMachineName}/*:*`,
            ],
            actions: ['states:RedriveExecution'],
          }),
        ],
      }),
    });

    // Add the policy to the state machine role
    props.stateMachineObj.role.attachInlinePolicy(distributedMapPolicy);

    // Will need a cdk nag suppression for this
    NagSuppressions.addResourceSuppressions(
      [props.stateMachineObj, distributedMapPolicy],
      [
        {
          id: 'AwsSolutions-IAM5',
          reason: 'Distributed Map IAM Policy requires asterisk in the resource ARN',
        },
      ],
      true
    );
  }

  /* If we have the step function handleIcav2AnalysisStateChange */
  /* We need to allow the durable lambda handleIcaEvent to start that step function */
  if (props.stateMachineName === 'handleIcav2AnalysisStateChange') {
    /* Get the lambda object */
    const handleIcaLambdaObject = <LambdaObject>(
      props.lambdaFunctions.find((lambdaObject) => lambdaObject.lambdaName === 'handleIcaEvent')
    );
    /* Grant permissions to the lambda object */
    props.stateMachineObj.grantStartExecution(handleIcaLambdaObject.lambdaFunction);

    /* We also need to add permissions for the queue url */

    NagSuppressions.addResourceSuppressions(
      props.stateMachineObj,
      [
        {
          id: 'AwsSolutions-IAM5',
          reason: 'Needs permissions to start execution',
        },
      ],
      true
    );
  }

  /*
  Handle ICAv2 Analysis State Change also requires permissions to launch other objects
   */
  if (sfnRequirements.needsNestedSfnStartExecutionPermissions) {
    if (props.stateMachineName == 'handleIcav2AnalysisStateChange') {
      for (const nestedSfnName of sfnNameList) {
        // For each of the active nested sfn functions
        switch (nestedSfnName) {
          case 'handleFilemanager':
          case 'handleNextflowFiles':
          case 'unlockCallbackId': {
            props.stateMachineObj.addToRolePolicy(
              new iam.PolicyStatement({
                actions: ['states:StartExecution', 'states:DescribeExecution'],
                resources: [
                  `arn:aws:states:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:stateMachine:${STACK_PREFIX}--${nestedSfnName}`,
                  `arn:aws:states:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:execution:${STACK_PREFIX}--${nestedSfnName}:*`,
                ],
              })
            );
            break;
          }
        }
      }
    }

    // Because we run a nested state machine, we need to add the permissions to the state machine role
    // See https://stackoverflow.com/questions/60612853/nested-step-function-in-a-step-function-unknown-error-not-authorized-to-cr
    props.stateMachineObj.addToRolePolicy(
      new iam.PolicyStatement({
        resources: [
          `arn:aws:events:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:rule/StepFunctionsGetEventsForStepFunctionsExecutionRule`,
        ],
        actions: ['events:PutTargets', 'events:PutRule', 'events:DescribeRule'],
      })
    );

    // Suppress IAM5: Wildcard needed because execution ARNs include dynamic IDs
    NagSuppressions.addResourceSuppressions(
      props.stateMachineObj,
      [
        {
          id: 'AwsSolutions-IAM5',
          reason:
            'Describe execution requires wildcard in resource ARN because execution IDs are dynamic',
        },
      ],
      true
    );
  }
}

function buildStepFunction(scope: Construct, props: SfnProps): SfnObjectProps {
  const sfnNameToSnakeCase = camelCaseToSnakeCase(props.stateMachineName);
  // const sfnRequirements = sfnToRequirementsMap[props.stateMachineName];

  /* Create the state machine definition substitutions */
  const stateMachine = new sfn.StateMachine(scope, `${props.stateMachineName}-sfn`, {
    stateMachineName: `${STACK_PREFIX}--${props.stateMachineName}`,
    definitionBody: sfn.DefinitionBody.fromFile(
      path.join(STEP_FUNCTIONS_DIR, sfnNameToSnakeCase + `_sfn_template.asl.json`)
    ),
    definitionSubstitutions: createStateMachineDefinitionSubstitutions(props),
  });

  /* Grant the state machine permissions */
  wireUpStateMachinePermissions(scope, {
    stateMachineObj: stateMachine,
    ...props,
  });

  /* Nag Suppressions */
  /* AwsSolutions-SF1 - We don't need ALL events to be logged */
  /* AwsSolutions-SF2 - We also don't need X-Ray tracing */
  NagSuppressions.addResourceSuppressions(
    stateMachine,
    [
      {
        id: 'AwsSolutions-SF1',
        reason: 'We do not need all events to be logged',
      },
      {
        id: 'AwsSolutions-SF2',
        reason: 'We do not need X-Ray tracing',
      },
    ],
    true
  );

  /* Return as a state machine object property */
  return {
    ...props,
    stateMachineObj: stateMachine,
  };
}

export function buildAllStepFunctions(scope: Construct, props: BuildSfnsProps): SfnObjectProps[] {
  // Initialize the step function objects
  const sfnObjects = [] as SfnObjectProps[];

  // Iterate over lambdaLayerToMapping and create the lambda functions
  for (const sfnName of sfnNameList) {
    sfnObjects.push(
      buildStepFunction(scope, {
        stateMachineName: sfnName,
        ...props,
      })
    );
  }

  return sfnObjects;
}
