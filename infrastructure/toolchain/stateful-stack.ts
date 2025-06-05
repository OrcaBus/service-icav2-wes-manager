import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { DeploymentStackPipeline } from '@orcabus/platform-cdk-constructs/deployment-stack-pipeline';
import { getStatefulStackProps } from '../stage/config';
import { REPO_NAME } from './constants';
import { StatefulApplicationStack } from '../stage/stateful-application-stack';

export class StatefulStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    new DeploymentStackPipeline(this, 'Icav2WesManagerStatefulDeployPipeline', {
      githubBranch: 'main',
      githubRepo: REPO_NAME,
      stack: StatefulApplicationStack,
      stackName: 'Icav2WesManagerStatefulDeployStack',
      stackConfig: {
        beta: getStatefulStackProps(),
        gamma: getStatefulStackProps(),
        prod: getStatefulStackProps(),
      },
      pipelineName: 'OrcaBus-Icav2WesManagerStatefulMicroservice',
      cdkSynthCmd: ['pnpm install --frozen-lockfile --ignore-scripts', 'pnpm cdk-stateful synth'],
    });
  }
}
