/* Lambda stuff */
import {
  BuildAllLambdasProps,
  BuildLambdaProps,
  lambdaNameList,
  LambdaObject,
  lambdaToRequirementsMap,
} from './interfaces';
import {
  DEFAULT_MAX_ICA_STATE_CHANGE_API_CONCURRENCY,
  DEFAULT_MAX_ICAV2_WES_REQUEST_API_CONCURRENCY,
  LAMBDA_DIR,
  STACK_PREFIX,
} from '../constants';
import { PythonUvFunction } from '@orcabus/platform-cdk-constructs/lambda';
import { Construct } from 'constructs';
import { camelCaseToSnakeCase } from '../utils';
import * as path from 'path';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import { NagSuppressions } from 'cdk-nag';
import { Duration } from 'aws-cdk-lib';
import { SqsEventSource } from 'aws-cdk-lib/aws-lambda-event-sources';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as cdk from 'aws-cdk-lib';

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
  const lambdaFunction = new PythonUvFunction(scope, `${props.lambdaName}-lambda`, {
    entry: path.join(LAMBDA_DIR, lambdaNameToSnakeCase + '_py'),
    runtime: lambda.Runtime.PYTHON_3_14,
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
    durableConfig: lambdaRequirements.needsDurableExecutionPermissions
      ? {
          executionTimeout: Duration.minutes(15),
          retentionPeriod: Duration.days(1),
        }
      : undefined,
  });

  // If the lambda has an SQS event source, we need to add this in
  // Generate Event Request uses the launch ICA Source Event Queue
  if (props.lambdaName === 'generateWesPostRequestFromEvent') {
    // Find the SQS queue from the props
    lambdaFunction.currentVersion.addEventSource(
      new SqsEventSource(props.generateWesPostRequestEventQueue, {
        maxConcurrency: DEFAULT_MAX_ICAV2_WES_REQUEST_API_CONCURRENCY,
        // Allow only one message per batch to be processed
        batchSize: 1,
      })
    );
  }

  // ICA State change lambda
  if (props.lambdaName === 'handleIcaEvent') {
    // Add the step function
    // Update the environment variable for the step function name
    // When we generate the state machine we will give the lambda permission to start the execution
    lambdaFunction.addEnvironment(
      'HANDLE_ICA_ANALYSIS_STATE_CHANGE_SFN_ARN',
      `arn:aws:states:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:stateMachine:${STACK_PREFIX}--${props.handleIcaStateChangeSfnName}`
    );

    // Find the SQS queue from the props
    lambdaFunction.currentVersion.addEventSource(
      new SqsEventSource(props.externalIcaEventQueue, {
        maxConcurrency: DEFAULT_MAX_ICA_STATE_CHANGE_API_CONCURRENCY,
        // Allow only one message per batch to be processed
        batchSize: 1,
        filters: [
          {
            pattern: JSON.stringify({
              body: {
                payload: {
                  tags: {
                    technicalTags: [
                      {
                        prefix: 'icav2_wes_orcabus_id=',
                      },
                    ],
                  },
                },
              },
            }),
          },
        ],
      })
    );
  }

  // If the lambda needs the test-data / ref-data permissions we need to add these in
  if (lambdaRequirements.needsTestDataBucketPermissions) {
    // Grant list permissions to the test data bucket
    props.testDataBucket.grantRead(lambdaFunction.currentVersion);

    NagSuppressions.addResourceSuppressions(
      lambdaFunction,
      [
        {
          id: 'AwsSolutions-IAM5',
          reason: 'Read-only access.', // Should be list-only, will fix later
          appliesTo: [
            // Read
            'Action::s3:GetObject*',
            'Action::s3:GetBucket*',
            // List
            'Action::s3:List*',
            // Bucket Resource
            `Resource::arn:<AWS::Partition>:s3:::${props.testDataBucket.bucketName}/*`,
          ],
        },
      ],
      true
    );
  }

  // If the lambda needs the test-data / ref-data permissions we need to add these in
  if (lambdaRequirements.needsReferenceDataBucketPermissions) {
    // Grant list permissions to the test data bucket
    props.referenceDataBucket.grantRead(lambdaFunction.currentVersion);

    NagSuppressions.addResourceSuppressions(
      lambdaFunction,
      [
        {
          id: 'AwsSolutions-IAM5',
          reason: 'Read-only access.', // Should be list-only, will fix later
          appliesTo: [
            // Read
            'Action::s3:GetObject*',
            'Action::s3:GetBucket*',
            // List
            'Action::s3:List*',
            // Bucket Resource
            `Resource::arn:<AWS::Partition>:s3:::${props.referenceDataBucket.bucketName}/*`,
          ],
        },
      ],
      true
    );
  }

  // If the lambda needs the permissions to write to the payloads bucket, we need to add these in
  if (lambdaRequirements.needsArtefactBucketPermissions) {
    // Grant write permissions to the payloads bucket
    props.artefactsBucket.grantReadWrite(lambdaFunction.currentVersion);

    // Add resource suppressions
    NagSuppressions.addResourceSuppressions(
      lambdaFunction,
      [
        {
          id: 'AwsSolutions-IAM5',
          reason: 'Read-write access.',
          appliesTo: [
            // Read
            'Action::s3:GetObject*',
            'Action::s3:GetBucket*',
            // List
            'Action::s3:List*',
            // Write
            'Action::s3:DeleteObject*',
            'Action::s3:Abort*',
            // Resources
            `Resource::arn:<AWS::Partition>:s3:::${props.artefactsBucket.bucketName}/*`,
          ],
        },
      ],
      true
    );

    // Update the environment variables for the artefacts bucket with the payloads and error logs prefixes
    lambdaFunction.addEnvironment(
      'S3_ANALYSIS_ARTEFACTS_BUCKET_NAME',
      props.artefactsBucket.bucketName
    );
    lambdaFunction.addEnvironment('S3_ANALYSIS_PAYLOAD_KEY_PREFIX', props.payloadsKeyPrefix);
    lambdaFunction.addEnvironment('S3_ANALYSIS_ERROR_LOGS_PREFIX', props.errorLogsKeyPrefix);
  }

  if (lambdaRequirements.needsCallbackPermissions) {
    // Grant write permissions to allow the lambda to unlock durable executions
    // We don't know the exact resource ARNs here since they are created dynamically
    lambdaFunction.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['lambda:SendDurableExecutionCallbackSuccess'],
        resources: [
          `arn:aws:lambda:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:function:*:*/durable-execution/*/*`,
        ],
      })
    );

    // Add resource suppressions
    NagSuppressions.addResourceSuppressions(
      lambdaFunction,
      [
        {
          id: 'AwsSolutions-IAM5',
          reason: 'Send DurableExecutionCallback success permissions to dynamic resources.',
          appliesTo: [
            'Resource::arn:aws:lambda:<AWS::Region>:<AWS::AccountId>:function:*:*/durable-execution/*/*',
          ],
        },
      ],
      true
    );
  }

  if (lambdaRequirements.needsCallbackDbPermissions) {
    // Grant write permissions to allow the lambda to update the callback database table
    props.callbackTable.grantReadWriteData(lambdaFunction.currentVersion);

    // Add the CALLBACK_DATABASE_NAME environment variable
    lambdaFunction.addEnvironment('CALLBACK_DATABASE_NAME', props.callbackTable.tableName);
  }

  /* Return the function */
  return {
    lambdaName: props.lambdaName,
    lambdaFunction: lambdaFunction,
  };
}
