// Standard cdk imports
import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';

// Application imports
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import * as secretsManager from 'aws-cdk-lib/aws-secretsmanager';
import * as events from 'aws-cdk-lib/aws-events';
import { IQueue } from 'aws-cdk-lib/aws-sqs';

// Local imports
import { StatelessApplicationStackConfig } from './interfaces';
import { NagSuppressions } from 'cdk-nag';
import { StageName } from '@orcabus/platform-cdk-constructs/shared-config/accounts';
import { buildAllLambdas } from './lambda';
import { buildAllStepFunctions } from './step-functions';
import { buildEventBridgeRules } from './event-rules';
import { buildAllEventBridgeTargets } from './event-targets';
import {
  addHttpRoutes,
  buildApiGateway,
  buildApiIntegration,
  buildApiInterfaceLambda,
} from './api';
import { buildAllEcsFargateTasks } from './ecs';

export type StatelessApplicationStackProps = StatelessApplicationStackConfig & cdk.StackProps;

// Stateless Application Stack
export class StatelessApplicationStack extends cdk.Stack {
  public readonly stageName: StageName;
  constructor(scope: Construct, id: string, props: StatelessApplicationStackProps) {
    super(scope, id, props);
    this.stageName = props.stageName;

    // Create the ssm parameter for this stack id
    new ssm.StringParameter(this, 'gitCommitId', {
      parameterName: `/cdk/git/${this.stackId}`,
      stringValue: process.env.CODEBUILD_RESOLVED_SOURCE_VERSION || 'unknown',
    });

    // Get dynamodb table (built in the stateful stack)
    const dynamodbTable = dynamodb.TableV2.fromTableName(this, props.tableName, props.tableName);

    // Extra tables
    const payloadsTable = dynamodb.TableV2.fromTableName(
      this,
      props.payloadsTableName,
      props.payloadsTableName
    );
    const callbackTable = dynamodb.TableV2.fromTableName(
      this,
      props.callbackTableName,
      props.callbackTableName
    );

    // Extra buckets
    const payloadsBucket = s3.Bucket.fromBucketName(
      this,
      props.payloadsBucketName,
      props.payloadsBucketName
    );

    // Get the event bus objects
    const externalEventBusObject = events.EventBus.fromEventBusName(
      this,
      props.externalEventBusName,
      props.externalEventBusName
    );
    const internalEventBusObject = events.EventBus.fromEventBusName(
      this,
      props.internalEventBusName,
      props.internalEventBusName
    );

    // SSM parameters
    const hostedZoneSsmParameterObj = ssm.StringParameter.fromStringParameterName(
      this,
      props.hostedZoneSsmParameterName,
      props.hostedZoneSsmParameterName
    );

    // Secrests
    const orcabusTokenSecretParameterObj = secretsManager.Secret.fromSecretNameV2(
      this,
      props.orcabusTokenSecretName,
      props.orcabusTokenSecretName
    );

    // Buckets - refdata and testData buckets
    const referenceDataBucket = s3.Bucket.fromBucketName(
      this,
      props.referenceDataBucketName,
      props.referenceDataBucketName
    );

    // Test data bucket
    const testDataBucket = s3.Bucket.fromBucketName(
      this,
      props.testDataBucketName,
      props.testDataBucketName
    );

    // Get the ICA WES Request SQS Queue from props
    const icav2WesRequestSqsQueue: IQueue = sqs.Queue.fromQueueArn(
      this,
      props.icav2WesRequestSqsQueueName,
      `arn:aws:sqs:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:${props.icav2WesRequestSqsQueueName}`
    );

    const icaExternalSqsQueue: IQueue = sqs.Queue.fromQueueArn(
      this,
      props.icaExternalSqsQueueName,
      `arn:aws:sqs:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:${props.icaExternalSqsQueueName}`
    );

    // Build the lambdas
    const lambdaObjects = buildAllLambdas(this, {
      artefactsBucket: payloadsBucket,
      payloadsKeyPrefix: props.payloadsKeyPrefix,
      errorLogsKeyPrefix: props.errorLogsKeyPrefix,
      referenceDataBucket: referenceDataBucket,
      testDataBucket: testDataBucket,
      generateWesPostRequestEventQueue: icav2WesRequestSqsQueue,
      externalIcaEventQueue: icaExternalSqsQueue,
      handleIcaStateChangeSfnName: 'handleIcav2AnalysisStateChange',
      callbackTable: callbackTable,
    });

    // Build the ecs tasks
    const ecsTasks = buildAllEcsFargateTasks(this, {
      hostnameSsmParameter: hostedZoneSsmParameterObj,
      orcabusTokenSecretObj: orcabusTokenSecretParameterObj,
    });

    // Build the step functions
    const stepFunctionObjects = buildAllStepFunctions(this, {
      lambdaFunctions: lambdaObjects,
      ecsTaskObjects: ecsTasks,
      eventBus: externalEventBusObject,
      eventSource: props.eventSource,
      payloadsTable: payloadsTable,
      callbackTable: callbackTable,
      icaExternalSqsQueue: icaExternalSqsQueue,
    });

    // Build event bridge rules
    const eventBridgeRuleObjects = buildEventBridgeRules(this, {
      /* Event buses */
      internalEventBus: internalEventBusObject,
      externalEventBus: externalEventBusObject,

      /* Event constants */
      icav2AnalysisStateChangeEventCode: props.icav2AnalysisStateChangeEventCode,
      icav2WesManagerTagKey: props.icav2WesManagerTagKey,
      icav2WesRequestDetailType: props.icav2WesRequestDetailType,
    });

    // Add the event-bridge rules
    buildAllEventBridgeTargets({
      eventBridgeRuleObjects: eventBridgeRuleObjects,
      sqsQueues: [icav2WesRequestSqsQueue],
    });

    // Build the API interface lambda
    const lambdaApi = buildApiInterfaceLambda(this, {
      /* Lambda props */
      lambdaName: 'icav2WesApiInterface',

      /* Table props */
      table: dynamodbTable,
      tableIndexNames: props.indexNames,

      /* Step functions triggered by the API */
      stepFunctions: stepFunctionObjects.filter((stepFunctionObject) =>
        ['launchIcav2Analysis', 'abortIcav2Analysis'].includes(stepFunctionObject.stateMachineName)
      ),

      /* Event bus */
      eventBus: externalEventBusObject,
      eventSource: props.eventSource,
      icav2WesAnalysisStateChangeEventDetail: props.icav2WesAnalysisStateChangeDetailType,

      /* SSM and Secrets */
      hostedZoneSsmParameter: hostedZoneSsmParameterObj,
    });

    // Build the API Gateway
    const apiGateway = buildApiGateway(this, props.apiGatewayCognitoProps);
    const apiIntegration = buildApiIntegration({
      lambdaFunction: lambdaApi,
    });
    addHttpRoutes(this, {
      apiGateway: apiGateway,
      apiIntegration: apiIntegration,
    });

    // Add in stack suppressions
    NagSuppressions.addStackSuppressions(this, [
      {
        id: 'AwsSolutions-IAM4',
        reason: 'We need to add this for the lambdas to work',
      },
    ]);
  }
}
