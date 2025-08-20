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

  /* Internal event stuff */
  internalEventBusName: string;
  internalEventBusDescription: string;
  icav2EventPipeName: string;
  slackTopicName: string;
}

export interface StatelessApplicationStackConfig extends cdk.StackProps {
  /* Stage name */
  stageName: StageName;

  /* Dynamodb table name */
  tableName: string;
  indexNames: string[];

  /* Extra tables */
  payloadsTableName: string;

  /* External event stuff */
  externalEventBusName: string;
  icav2WesRequestDetailType: string;
  icav2WesAnalysisStateChangeDetailType: string;
  icav2DataCopySyncDetailType: string;
  eventSource: string;

  /* Internal event stuff */
  internalEventBusName: string;
  icav2EventPipeName: string;
  icav2AnalysisStateChangeEventCode: string;
  icav2WesManagerTagKey: string;

  /* SSM - Secrets */
  hostedZoneSsmParameterName: string;
  icav2AccessTokenSecretId: string;

  /* API Stuff */
  apiGatewayCognitoProps: OrcaBusApiGatewayProps;
}
