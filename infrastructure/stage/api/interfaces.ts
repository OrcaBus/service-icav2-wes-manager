import { ITableV2 } from 'aws-cdk-lib/aws-dynamodb';
import { IEventBus } from 'aws-cdk-lib/aws-events';
import { PythonFunction } from '@aws-cdk/aws-lambda-python-alpha';
import { OrcaBusApiGateway } from '@orcabus/platform-cdk-constructs/api-gateway';
import { HttpLambdaIntegration } from 'aws-cdk-lib/aws-apigatewayv2-integrations';
import { SfnObjectProps } from '../step-functions/interfaces';
import { IStringParameter } from 'aws-cdk-lib/aws-ssm';
import { IQueue } from 'aws-cdk-lib/aws-sqs';

export interface LambdaApiProps {
  /* The lambda name */
  lambdaName: string;

  /* Table to use */
  table: ITableV2;
  tableIndexNames: string[];

  /* Step Functions */
  stepFunctions: SfnObjectProps[];
  sqsQueues: IQueue[];

  /* Event Bus */
  eventBus: IEventBus;
  eventSource: string;
  icav2WesAnalysisStateChangeEventDetail: string;

  /* SSM Parameters */
  hostedZoneSsmParameter: IStringParameter;
}

/** API Interfaces */
/** API Gateway interfaces **/
export interface BuildApiIntegrationProps {
  lambdaFunction: PythonFunction;
}

export interface BuildHttpRoutesProps {
  apiGateway: OrcaBusApiGateway;
  apiIntegration: HttpLambdaIntegration;
}
