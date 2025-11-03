/* Event Bridge Target Stuff */
import * as eventsTargets from 'aws-cdk-lib/aws-events-targets';
import * as events from 'aws-cdk-lib/aws-events';

import {
  AddLambdaAsEventBridgeTargetProps,
  eventBridgeTargetsNameList,
  EventBridgeTargetsProps,
} from './interfaces';

function buildLambdaEventBridgeTargetWithInputAsDetail(
  props: AddLambdaAsEventBridgeTargetProps
): void {
  props.eventBridgeRuleObj.addTarget(
    new eventsTargets.LambdaFunction(props.lambdaFunction.lambdaFunction, {
      event: events.RuleTargetInput.fromEventPath('$.detail'),
    })
  );
}

export function buildAllEventBridgeTargets(props: EventBridgeTargetsProps): void {
  /* Iterate over each event bridge rule and add the target */
  for (const eventBridgeTargetsName of eventBridgeTargetsNameList) {
    switch (eventBridgeTargetsName) {
      case 'icav2WesPostRequestTargetToGenerateWesPostRequestLambda': {
        buildLambdaEventBridgeTargetWithInputAsDetail(<AddLambdaAsEventBridgeTargetProps>{
          eventBridgeRuleObj: props.eventBridgeRuleObjects.find(
            (eventBridgeObject) => eventBridgeObject.ruleName === 'icav2WesPostRequestRule'
          )?.ruleObject,
          lambdaFunction: props.lambdaObjects.find(
            (eventBridgeObject) =>
              eventBridgeObject.lambdaName === 'generateWesPostRequestFromEvent'
          ),
        });
        break;
      }
    }
  }
}
