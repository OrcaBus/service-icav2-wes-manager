/*
Build the ecs fargate task
*/

import { Construct } from 'constructs';
import {
  CPU_ARCHITECTURE_MAP,
  EcsFargateTaskConstruct,
} from '@orcabus/platform-cdk-constructs/ecs';
import * as path from 'path';
import { ECS_DIR } from '../constants';
import {
  BuildAllFargateEcsTasksProps,
  BuildFargateEcsTaskProps,
  ecsTaskNameList,
  EcsTaskObject,
} from './interfaces';
import { NagSuppressions } from 'cdk-nag';
import { camelCaseToSnakeCase } from '../utils';

function buildEcsFargateTask(scope: Construct, props: BuildFargateEcsTaskProps) {
  /*
  Generate an ECS Fargate task construct with the provided properties.
  */

  const ecsTask = new EcsFargateTaskConstruct(scope, `${props.taskName}-ecs`, {
    containerName: props.taskName,
    dockerPath: path.join(ECS_DIR, camelCaseToSnakeCase(props.taskName)),
    nCpus: 2, // 2 CPUs
    memoryLimitGiB: 16, // 16 GB of memory (maximum for 2 CPUs)
    architecture: 'ARM64',
    runtimePlatform: CPU_ARCHITECTURE_MAP['ARM64'],
  });

  // Needs access to ORCABUS_TOKEN_SECRET_ID and HOSTNAME_SSM_PARAMETER_NAME
  props.orcabusTokenSecretObj.grantRead(ecsTask.taskDefinition.taskRole);
  ecsTask.containerDefinition.addEnvironment(
    'ORCABUS_TOKEN_SECRET_ID',
    props.orcabusTokenSecretObj.secretName
  );
  props.hostnameSsmParameter.grantRead(ecsTask.taskDefinition.taskRole);
  ecsTask.containerDefinition.addEnvironment(
    'HOSTNAME_SSM_PARAMETER_NAME',
    props.hostnameSsmParameter.parameterName
  );

  // Add suppressions for the task role
  // Since the task role needs to access the S3 bucket prefix
  NagSuppressions.addResourceSuppressions(
    [ecsTask.taskDefinition, ecsTask.taskExecutionRole],
    [
      {
        id: 'AwsSolutions-IAM5',
        reason: 'The task role needs to access secrets manager.',
      },
      {
        id: 'AwsSolutions-IAM4',
        reason:
          'We use the standard ecs task role for this task, which allows the guard duty agent to run alongside the task.',
      },
      {
        id: 'AwsSolutions-ECS2',
        reason:
          'The task is designed to run with some constant environment variables, not sure why this is a bad thing?',
      },
    ],
    true
  );

  return {
    taskName: props.taskName,
    ecsFargateTaskConstruct: ecsTask,
  };
}

export function buildAllEcsFargateTasks(
  scope: Construct,
  props: BuildAllFargateEcsTasksProps
): EcsTaskObject[] {
  // Iterate over lambdaLayerToMapping and create the lambda functions
  const ecsTaskObjects: EcsTaskObject[] = [];
  for (const ecsTaskName of ecsTaskNameList) {
    ecsTaskObjects.push(
      buildEcsFargateTask(scope, {
        ...props,
        taskName: ecsTaskName,
      })
    );
  }

  return ecsTaskObjects;
}
