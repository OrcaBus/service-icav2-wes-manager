/* Lambda stuff */
import {
  BuildLambdaProps,
  lambdaNameList,
  LambdaObject,
  lambdaToRequirementsMap,
} from './interfaces';
import { LAMBDA_DIR } from '../constants';
import { PythonUvFunction } from '@orcabus/platform-cdk-constructs/lambda';
import { Construct } from 'constructs';
import { camelCaseToSnakeCase } from '../utils';
import * as path from 'path';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import { NagSuppressions } from 'cdk-nag';
import { Duration } from 'aws-cdk-lib';

export function buildAllLambdas(scope: Construct): LambdaObject[] {
  // Iterate over lambdaLayerToMapping and create the lambda functions
  const lambdaObjects: LambdaObject[] = [];
  for (const lambdaName of lambdaNameList) {
    lambdaObjects.push(
      buildLambda(scope, {
        lambdaName: lambdaName,
      })
    );
  }

  return lambdaObjects;
}

/** Lambda stuff */
function buildLambda(scope: Construct, props: BuildLambdaProps): LambdaObject {
  const lambdaNameToSnakeCase = camelCaseToSnakeCase(props.lambdaName);
  const lambdaRequirements = lambdaToRequirementsMap[props.lambdaName];

  // Create the lambda function
  const lambdaFunction = new PythonUvFunction(scope, props.lambdaName, {
    entry: path.join(LAMBDA_DIR, lambdaNameToSnakeCase + '_py'),
    runtime: lambda.Runtime.PYTHON_3_12,
    architecture: lambda.Architecture.ARM_64,
    index: lambdaNameToSnakeCase + '.py',
    handler: 'handler',
    timeout: Duration.seconds(60),
    memorySize: 2048,
    includeIcav2Layer: lambdaRequirements.needsIcav2ToolkitLayer,
    includeOrcabusApiToolsLayer: lambdaRequirements.needsOrcabusTookitLayer,
  });

  // AwsSolutions-L1 - We'll migrate to PYTHON_3_13 ASAP, soz
  // AwsSolutions-IAM4 - We need to add this for the lambda to work
  NagSuppressions.addResourceSuppressions(
    lambdaFunction,
    [
      {
        id: 'AwsSolutions-L1',
        reason: 'Will migrate to PYTHON_3_13 ASAP, soz',
      },
    ],
    true
  );

  /* Return the function */
  return {
    lambdaName: props.lambdaName,
    lambdaFunction: lambdaFunction,
  };
}
