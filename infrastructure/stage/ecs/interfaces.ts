/*
Interfaces
*/

import { IParameter } from 'aws-cdk-lib/aws-ssm';
import { ISecret } from 'aws-cdk-lib/aws-secretsmanager';
import { EcsFargateTaskConstruct } from '@orcabus/platform-cdk-constructs/ecs';

export type EcsTaskName = 'validateBamFile';

export const ecsTaskNameList: EcsTaskName[] = ['validateBamFile'];

export interface BuildAllFargateEcsTasksProps {
  orcabusTokenSecretObj: ISecret;
  hostnameSsmParameter: IParameter;
}

export interface BuildFargateEcsTaskProps extends BuildAllFargateEcsTasksProps {
  taskName: EcsTaskName;
}

export interface EcsTaskObject {
  taskName: EcsTaskName;
  ecsFargateTaskConstruct: EcsFargateTaskConstruct;
}
