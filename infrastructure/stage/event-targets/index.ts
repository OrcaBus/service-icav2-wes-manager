/* Event Bridge Target Stuff */
import * as eventsTargets from 'aws-cdk-lib/aws-events-targets';
import * as events from 'aws-cdk-lib/aws-events';

import {
  AddSqsAsEventBridgeTargetProps,
  eventBridgeTargetsNameList,
  EventBridgeTargetsProps,
} from './interfaces';

function buildSqsEventBridgeTargetWithInputAsDetail(props: AddSqsAsEventBridgeTargetProps): void {
  props.eventBridgeRuleObj.addTarget(
    new eventsTargets.SqsQueue(props.sqsQueue, {
      message: events.RuleTargetInput.fromEventPath('$.detail'),
    })
  );
}

export function buildAllEventBridgeTargets(props: EventBridgeTargetsProps): void {
  /* Iterate over each event bridge rule and add the target */
  for (const eventBridgeTargetsName of eventBridgeTargetsNameList) {
    switch (eventBridgeTargetsName) {
      case 'icav2WesPostRequestTargetToGenerateWesPostRequestSqsQueue': {
        buildSqsEventBridgeTargetWithInputAsDetail(<AddSqsAsEventBridgeTargetProps>{
          eventBridgeRuleObj: props.eventBridgeRuleObjects.find(
            (eventBridgeObject) => eventBridgeObject.ruleName === 'icav2WesPostRequestRule'
          )?.ruleObject,
          sqsQueue: props.sqsQueues.find(
            (sqsObject) => sqsObject.queueName === 'Icav2WesRequestSqsQueue'
          ),
        });
        break;
      }
    }
  }
}
