import * as cdk from 'aws-cdk-lib';
import { EventPattern, IEventBus, Rule } from 'aws-cdk-lib/aws-events';
import { PythonFunction } from '@aws-cdk/aws-lambda-python-alpha';

import { ITableV2 } from 'aws-cdk-lib/aws-dynamodb';
import { StateMachine } from 'aws-cdk-lib/aws-stepfunctions';
import { Queue } from 'aws-cdk-lib/aws-sqs';
import { Duration } from 'aws-cdk-lib';

import {
  OrcaBusApiGateway,
  OrcaBusApiGatewayProps,
} from '@orcabus/platform-cdk-constructs/api-gateway';
import { HttpLambdaIntegration } from 'aws-cdk-lib/aws-apigatewayv2-integrations';

/** Application Interfaces */
export interface StatefulApplicationStackConfig extends cdk.StackProps {
  /* Dynamodb table name */
  tableName: string;
  indexNames: string[];

  /* Internal event stuff */
  internalEventBusName: string;
  internalEventBusDescription: string;
  icav2EventPipeName: string;
  slackTopicName: string;
}

export interface StatelessApplicationStackConfig extends cdk.StackProps {
  /* Dynamodb table name */
  tableName: string;
  indexNames: string[];

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

  /* API Stuff */
  apiGatewayCognitoProps: OrcaBusApiGatewayProps;
}

/** Stateful Interfaces */

export interface BuildICAv2WesDbProps {
  /* The name of the table */
  tableName: string;

  /* The names of the indexes */
  indexNames: string[];
}

export interface BuildICAv2EventBusProps {
  /* The name of the event bus */
  eventBusName: string;
  /* The description of the event bus */
  eventBusDescription: string;
}

/** Stateful interfaces **/

/** Stateful interfaces **/
export interface IcaSqsQueueConstructProps {
  /* The name for the incoming SQS queue (the DLQ with use this name with a "-dlq" postfix) */
  icaQueueName: string;
  /* The visibility timeout for the queue */
  icaQueueVizTimeout: Duration;
  /* The ARN of the SNS Topic to receive DLQ notifications from CloudWatch */
  slackTopicArn: string;
  /* The CloudWatch Alarm threshold to use before raising an alarm */
  dlqMessageThreshold: number;
  /* The ICA account to grant publish permissions to */
  icaAwsAccountNumber: string;
}

export interface IcaEventPipeConstructProps {
  /* The Sqs object */
  icaSqsQueue: Queue;
  /* The name for the Event Pipe */
  icaEventPipeName: string;
  /* The Event Bus to forward events to (used to lookup the Event Bus) */
  eventBusObj: IEventBus;
}

export type IcaSqsEventPipeProps = Omit<IcaEventPipeConstructProps, 'icaSqsQueue'> &
  IcaSqsQueueConstructProps;

/** Stateless Interfaces */

export type LambdaNameList =
  | 'abortAnalysis'
  | 'deleteIcav2Dir'
  | 'generateWesPostRequestFromEvent'
  | 'getIcav2WesObject'
  | 'getLogsDir'
  | 'launchIcav2AnalysisViaWrapica'
  | 'updateStatusOnWesApi';

/* Lambda names array */
/* Bit of double handling, BUT types are not parsed to JS */
export const lambdaNameList: Array<LambdaNameList> = [
  'abortAnalysis',
  'deleteIcav2Dir',
  'generateWesPostRequestFromEvent',
  'getIcav2WesObject',
  'getLogsDir',
  'launchIcav2AnalysisViaWrapica',
  'updateStatusOnWesApi',
];

/* We also throw in our custom application interfaces here too */
export interface LambdaRequirementProps {
  needsIcav2ToolkitLayer?: boolean;
  needsOrcabusTookitLayer?: boolean;
}

export type LambdaToRequirementsMapType = { [key in LambdaNameList]: LambdaRequirementProps };

export const lambdaToRequirementsMap: LambdaToRequirementsMapType = {
  abortAnalysis: {
    needsIcav2ToolkitLayer: true,
  },
  deleteIcav2Dir: {
    needsIcav2ToolkitLayer: true,
  },
  generateWesPostRequestFromEvent: {
    needsOrcabusTookitLayer: true,
  },
  getIcav2WesObject: {
    needsOrcabusTookitLayer: true,
  },
  getLogsDir: {
    needsIcav2ToolkitLayer: true,
  },
  launchIcav2AnalysisViaWrapica: {
    needsIcav2ToolkitLayer: true,
  },
  updateStatusOnWesApi: {
    needsOrcabusTookitLayer: true,
  },
};

export interface BuildLambdaProps {
  lambdaName: LambdaNameList;
}

export interface LambdaObject extends BuildLambdaProps {
  lambdaFunction: PythonFunction;
}

/** Step Function interfaces */

export type SfnNameList =
  | 'abortIcav2Analysis'
  | 'handleIcav2AnalysisStateChange'
  | 'launchIcav2Analysis';

export const sfnNameList: Array<SfnNameList> = [
  'abortIcav2Analysis',
  'handleIcav2AnalysisStateChange',
  'launchIcav2Analysis',
];

export interface BuildSfnsProps {
  /* Naming formation */
  lambdaFunctions: Array<LambdaObject>;

  /* The event bus to use */
  eventBus: IEventBus;
  eventSource: string;
  icav2DataCopySyncDetail: string;
}

export interface SfnProps extends BuildSfnsProps {
  /* Naming formation */
  stateMachineName: SfnNameList;
}

export interface SfnObjectProps extends SfnProps {
  /* The state machine object */
  stateMachineObj: StateMachine;
}

export const stepFunctionToLambdaMap: { [key in SfnNameList]: Array<LambdaNameList> } = {
  abortIcav2Analysis: ['abortAnalysis'],
  handleIcav2AnalysisStateChange: [
    'deleteIcav2Dir',
    'updateStatusOnWesApi',
    'getLogsDir',
    'getIcav2WesObject',
  ],
  launchIcav2Analysis: ['launchIcav2AnalysisViaWrapica', 'updateStatusOnWesApi'],
};

export interface SfnRequirementsProps {
  /*
    Event Bus Stuff - required only for the handleIcav2AnalysisStateChange state machine
    This state machine needs to put permissions on the external event bus
    in order to copy the log files into the proper location
    */
  needsExternalEventBusPutPermissions?: boolean;
}

export type SfnToRequirementsMapType = { [key in SfnNameList]: SfnRequirementsProps };

export const sfnToRequirementsMap: SfnToRequirementsMapType = {
  abortIcav2Analysis: {
    needsExternalEventBusPutPermissions: false,
  },
  handleIcav2AnalysisStateChange: {
    needsExternalEventBusPutPermissions: true,
  },
  launchIcav2Analysis: {
    needsExternalEventBusPutPermissions: false,
  },
};

/** Event bridge rules interfaces */

export type EventBridgeRuleNameList =
  // Internal rule - for running analyses
  | 'icav2AnalysisStateChangeRule'
  // External rule - for requests to run analyses
  | 'icav2WesPostRequestRule';

export const eventBridgeRuleNameList: Array<EventBridgeRuleNameList> = [
  'icav2AnalysisStateChangeRule',
  'icav2WesPostRequestRule',
];

export interface Icav2AnalysisStateChangeRuleEventPatternProps {
  icav2AnalysisStateChangeEventCode: string;
  icav2WesManagerTagKey: string;
}

export interface Icav2WesPostRequestTargetRuleEventPatternProps {
  icav2WesRequestDetailType: string;
}

export interface EventBridgeRuleProps {
  ruleName: EventBridgeRuleNameList;
  eventBus: IEventBus;
  eventPattern: EventPattern;
}

export interface EventBridgeRuleObject {
  ruleName: EventBridgeRuleNameList;
  ruleObject: Rule;
}

export type BuildIcav2AnalysisStateChangeRuleProps = Omit<
  Icav2AnalysisStateChangeRuleEventPatternProps & EventBridgeRuleProps,
  'eventPattern'
>;
export type buildIcav2WesPostRequestRuleProps = Omit<
  Icav2WesPostRequestTargetRuleEventPatternProps & EventBridgeRuleProps,
  'eventPattern'
>;

export interface BuildEventBridgeRulesProps {
  /* Event Buses */
  internalEventBus: IEventBus;
  externalEventBus: IEventBus;

  /* Event Patterns - Analysis State Change rule */
  icav2AnalysisStateChangeEventCode: string;
  icav2WesManagerTagKey: string;

  /* Event Patterns - Wes Post Request rule */
  icav2WesRequestDetailType: string;
}

/** Event bridge targets interfaces */

export type EventBridgeTargetsNameList =
  | 'icav2AnalysisStateChangeTargetToHandleStateChangeSfn'
  | 'icav2WesPostRequestTargetToGenerateWesPostRequestLambda';

export const eventBridgeTargetsNameList: Array<EventBridgeTargetsNameList> = [
  'icav2AnalysisStateChangeTargetToHandleStateChangeSfn',
  'icav2WesPostRequestTargetToGenerateWesPostRequestLambda',
];

export interface EventBridgeTargetsProps {
  eventBridgeRuleObjects: EventBridgeRuleObject[];
  stepFunctionObjects: SfnObjectProps[];
  lambdaObjects: LambdaObject[];
}

export interface AddSfnAsEventBridgeTargetProps {
  stateMachineObj: StateMachine;
  eventBridgeRuleObj: Rule;
}

export interface AddLambdaAsEventBridgeTargetProps {
  lambdaFunction: LambdaObject;
  eventBridgeRuleObj: Rule;
}

/** API Interfaces Props */

export interface LambdaApiProps {
  /* The lambda name */
  lambdaName: string;

  /* Table to use */
  table: ITableV2;
  tableIndexNames: string[];

  /* Step Functions */
  stepFunctions: SfnObjectProps[];

  /* Event Bus */
  eventBus: IEventBus;
  eventSource: string;
  icav2WesAnalysisStateChangeEventDetail: string;
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
