import * as cdk from 'aws-cdk-lib';
import { OrcaBusApiGatewayProps } from '@orcabus/platform-cdk-constructs/api-gateway';
import { StageName } from '@orcabus/platform-cdk-constructs/shared-config/accounts';

/** Application Interfaces */
export interface StatefulApplicationStackConfig extends cdk.StackProps {
  /* Dynamodb table name */
  tableName: string;
  indexNames: string[];

  /* Extra tables */
  payloadsTableName: string;

  /* Extra buckets */
  payloadsBucketName: string;

  /* Internal event stuff */
  internalEventBusName: string;
  internalEventBusDescription: string;

  /* SQS Stuff */
  slackTopicName: string;
  /* Launch name / event pipe stuff */
  launchIcaAnalysisSqsQueueName: string;
  launchIcaAnalysisEventPipeName: string;
  /* External sqs name / event pipe stuff */
  icaExternalSqsQueueName: string;
  icaExternalEventPipeName: string;
}

export interface StatelessApplicationStackConfig extends cdk.StackProps {
  /* Stage name */
  stageName: StageName;

  /* Dynamodb table name */
  tableName: string;
  indexNames: string[];

  /* Extra tables */
  payloadsTableName: string;

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
  icaExternalEventPipeName: string;
  icav2AnalysisStateChangeEventCode: string;
  icav2WesManagerTagKey: string;
  launchIcaAnalysisSqsQueueName: string;

  /* SSM - Secrets */
  hostedZoneSsmParameterName: string;
  icav2AccessTokenSecretId: string;

  /* API Stuff */
  apiGatewayCognitoProps: OrcaBusApiGatewayProps;
}
