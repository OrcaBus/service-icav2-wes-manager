import {
  BuildEventBridgeRulesProps,
  buildIcav2WesPostRequestRuleProps,
  eventBridgeRuleNameList,
  EventBridgeRuleObject,
  EventBridgeRuleProps,
  Icav2WesPostRequestTargetRuleEventPatternProps,
} from './interfaces';
import { Rule } from 'aws-cdk-lib/aws-events';
import { Construct } from 'constructs';
import * as events from 'aws-cdk-lib/aws-events';

/** Event bridge rules stuff */
function buildIcav2WesPostRequestTarget(props: Icav2WesPostRequestTargetRuleEventPatternProps) {
  return {
    detailType: [props.icav2WesRequestDetailType],
  };
}

function buildEventRule(scope: Construct, props: EventBridgeRuleProps): Rule {
  return new events.Rule(scope, props.ruleName, {
    ruleName: props.ruleName,
    eventPattern: props.eventPattern,
    eventBus: props.eventBus,
  });
}

function buildIcav2WesPostRequestRule(
  scope: Construct,
  props: buildIcav2WesPostRequestRuleProps
): Rule {
  return buildEventRule(scope, {
    ruleName: props.ruleName,
    eventPattern: buildIcav2WesPostRequestTarget(props),
    eventBus: props.eventBus,
  });
}

export function buildEventBridgeRules(
  scope: Construct,
  props: BuildEventBridgeRulesProps
): EventBridgeRuleObject[] {
  const eventBridgeObjects: EventBridgeRuleObject[] = [];
  for (const eventBridgeRuleName of eventBridgeRuleNameList) {
    switch (eventBridgeRuleName) {
      case 'icav2WesPostRequestRule': {
        eventBridgeObjects.push({
          ruleName: eventBridgeRuleName,
          ruleObject: buildIcav2WesPostRequestRule(scope, {
            ruleName: eventBridgeRuleName,
            eventBus: props.externalEventBus,
            icav2WesRequestDetailType: props.icav2WesRequestDetailType,
          }),
        });
        break;
      }
    }
  }
  return eventBridgeObjects;
}
