import { StateMachine } from 'aws-cdk-lib/aws-stepfunctions';
import { Rule } from 'aws-cdk-lib/aws-events';
import { EventBridgeRuleObject } from '../event-rules/interfaces';
import { SfnObjectProps } from '../step-functions/interfaces';
import { LambdaObject } from '../lambda/interfaces';

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
