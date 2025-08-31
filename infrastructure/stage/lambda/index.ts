/* Lambda stuff */
import {
  BuildAllLambdasProps,
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

export function buildAllLambdas(scope: Construct, props: BuildAllLambdasProps): LambdaObject[] {
  // Iterate over lambdaLayerToMapping and create the lambda functions
  const lambdaObjects: LambdaObject[] = [];
  for (const lambdaName of lambdaNameList) {
    lambdaObjects.push(
      buildLambda(scope, {
        lambdaName: lambdaName,
        ...props,
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
    // We need a longer timeout for the launchIcav2AnalysisViaWrapica lambda
    timeout:
      props.lambdaName === 'launchIcav2AnalysisViaWrapica'
        ? Duration.minutes(15)
        : Duration.seconds(60),
    // And if we have a lot of data to process, we need more memory
    memorySize: props.lambdaName === 'launchIcav2AnalysisViaWrapica' ? 4096 : 2048,
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

  // If the lambda needs the test-data / ref-data permissions we need to add these in
  if (lambdaRequirements.needsTestDataBucketPermissions) {
    // Grant list permissions to the test data bucket
    props.testDataBucket.grantRead(lambdaFunction.currentVersion);

    NagSuppressions.addResourceSuppressions(lambdaFunction, [
      {
        id: 'AwsSolutions-IAM5',
        reason: 'Read-only access.', // Should be list-only, will fix later
      },
    ]);
  }

  // If the lambda needs the test-data / ref-data permissions we need to add these in
  if (lambdaRequirements.needsReferenceDataBucketPermissions) {
    // Grant list permissions to the test data bucket
    props.referenceDataBucket.grantRead(lambdaFunction.currentVersion);

    NagSuppressions.addResourceSuppressions(lambdaFunction, [
      {
        id: 'AwsSolutions-IAM5',
        reason: 'Read-only access.', // Should be list-only, will fix later
      },
    ]);
  }

  // If the lambda needs the permissions to write to the payloads bucket, we need to add these in
  if (lambdaRequirements.needsPayloadsBucketPermissions) {
    // Grant write permissions to the payloads bucket
    props.payloadsBucket.grantReadWrite(lambdaFunction.currentVersion);

    // Add resource suppressions
    NagSuppressions.addResourceSuppressions(lambdaFunction, [
      {
        id: 'AwsSolutions-IAM5',
        reason: 'Read-write access.',
      },
    ]);

    // Update the environment variables for the payloads bucket
    lambdaFunction.addEnvironment(
      'S3_ANALYSIS_PAYLOAD_BUCKET_NAME',
      props.payloadsBucket.bucketName
    );
    lambdaFunction.addEnvironment('S3_ANALYSIS_PAYLOAD_KEY_PREFIX', props.payloadsKeyPrefix);
  }

  /* Return the function */
  return {
    lambdaName: props.lambdaName,
    lambdaFunction: lambdaFunction,
  };
}
