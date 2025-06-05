/* Event Bridge Target Stuff */
import * as eventsTargets from 'aws-cdk-lib/aws-events-targets';
import * as events from 'aws-cdk-lib/aws-events';

import {
  AddLambdaAsEventBridgeTargetProps,
  AddSfnAsEventBridgeTargetProps,
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

function buildSfnEventBridgeTargetFromIcaEventPipe(props: AddSfnAsEventBridgeTargetProps): void {
  props.eventBridgeRuleObj.addTarget(
    new eventsTargets.SfnStateMachine(props.stateMachineObj, {
      input: events.RuleTargetInput.fromEventPath('$.detail.ica-event.payload'),
    })
  );
}

export function buildAllEventBridgeTargets(props: EventBridgeTargetsProps): void {
  /* Iterate over each event bridge rule and add the target */
  for (const eventBridgeTargetsName of eventBridgeTargetsNameList) {
    switch (eventBridgeTargetsName) {
      case 'icav2AnalysisStateChangeTargetToHandleStateChangeSfn': {
        buildSfnEventBridgeTargetFromIcaEventPipe(<AddSfnAsEventBridgeTargetProps>{
          eventBridgeRuleObj: props.eventBridgeRuleObjects.find(
            (eventBridgeObject) => eventBridgeObject.ruleName === 'icav2AnalysisStateChangeRule'
          )?.ruleObject,
          stateMachineObj: props.stepFunctionObjects.find(
            (eventBridgeObject) =>
              eventBridgeObject.stateMachineName === 'handleIcav2AnalysisStateChange'
          )?.stateMachineObj,
        });
        break;
      }
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
