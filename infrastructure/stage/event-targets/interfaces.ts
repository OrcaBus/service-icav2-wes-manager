import { Rule } from 'aws-cdk-lib/aws-events';
import { EventBridgeRuleObject } from '../event-rules/interfaces';
import { IQueue } from 'aws-cdk-lib/aws-sqs';

export type EventBridgeTargetsNameList =
  // Post Request to WES Lambda
  'icav2WesPostRequestTargetToGenerateWesPostRequestSqsQueue';

export const eventBridgeTargetsNameList: Array<EventBridgeTargetsNameList> = [
  // Post Request to WES Lambda
  'icav2WesPostRequestTargetToGenerateWesPostRequestSqsQueue',
];

export interface EventBridgeTargetsProps {
  eventBridgeRuleObjects: EventBridgeRuleObject[];
  sqsQueues: IQueue[];
}

export interface AddSqsAsEventBridgeTargetProps {
  sqsQueue: IQueue;
  eventBridgeRuleObj: Rule;
}
