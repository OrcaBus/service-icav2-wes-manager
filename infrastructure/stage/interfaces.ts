import * as cdk from 'aws-cdk-lib';
import { OrcaBusApiGatewayProps } from '@orcabus/platform-cdk-constructs/api-gateway';
import { StageName } from '@orcabus/platform-cdk-constructs/shared-config/accounts';
import { EventBridgeRuleName } from './event-rules/interfaces';

/** Application Interfaces */
export interface StatefulApplicationStackConfig extends cdk.StackProps {
  /* Dynamodb table name */
  wesTableName: string;
  indexNames: string[];

  /* Extra tables */
  payloadsTableName: string;
  callbackTableName: string;

  /* Extra buckets */
  payloadsBucketName: string;

  /* Main Event Stuff */
  externalEventBusName: string;

  /* Internal event stuff */
  internalEventBusName: string;
  internalEventBusDescription: string;

  /* SQS Stuff */
  slackTopicName: string;

  /* ICAv2 WES Request stuff */
  icav2WesRequestEventRuleName: EventBridgeRuleName;
  icav2WesRequestSqsQueueName: string;

  /* External sqs name */
  icaExternalSqsQueueName: string;
}

export interface StatelessApplicationStackConfig extends cdk.StackProps {
  /* Stage name */
  stageName: StageName;

  /* Dynamodb table name */
  tableName: string;
  indexNames: string[];

  /* Extra tables */
  payloadsTableName: string;
  callbackTableName: string;

  /* Extra buckets */
  payloadsBucketName: string;
  payloadsKeyPrefix: string;
  errorLogsKeyPrefix: string;

  /* External event stuff */
  externalEventBusName: string;
  icav2WesRequestDetailType: string;
  icav2WesAnalysisStateChangeDetailType: string;
  eventSource: string;

  /* External bucket stuff */
  testDataBucketName: string;
  referenceDataBucketName: string;

  /* Internal event stuff */
  internalEventBusName: string;
  icav2AnalysisStateChangeEventCode: string;
  icav2WesManagerTagKey: string;
  icav2WesRequestSqsQueueName: string;
  icaExternalSqsQueueName: string;

  /* SSM - Secrets */
  hostedZoneSsmParameterName: string;
  orcabusTokenSecretName: string;
  icav2AccessTokenSecretId: string;

  /* API Stuff */
  apiGatewayCognitoProps: OrcaBusApiGatewayProps;
}
