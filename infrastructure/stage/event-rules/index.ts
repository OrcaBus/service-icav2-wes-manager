import {
  BuildEventBridgeRulesProps,
  BuildIcav2AnalysisStateChangeRuleProps,
  buildIcav2WesPostRequestRuleProps,
  eventBridgeRuleNameList,
  EventBridgeRuleObject,
  EventBridgeRuleProps,
  Icav2AnalysisStateChangeRuleEventPatternProps,
  Icav2WesPostRequestTargetRuleEventPatternProps,
} from './interfaces';
import { EventPattern } from 'aws-cdk-lib/aws-events/lib/event-pattern';
import { Rule } from 'aws-cdk-lib/aws-events';
import { Construct } from 'constructs';
import * as events from 'aws-cdk-lib/aws-events';

/** Event bridge rules stuff */
function buildIcav2AnalysisStateChangeEventPattern(
  props: Icav2AnalysisStateChangeRuleEventPatternProps
): EventPattern {
  return {
    detail: {
      'ica-event': {
        // ICA_EXEC_028 is an analysis state change in ICAv2
        eventCode: [props.icav2AnalysisStateChangeEventCode],
        payload: {
          tags: {
            technicalTags: [
              {
                prefix: props.icav2WesManagerTagKey,
              },
            ],
          },
        },
      },
    },
  };
}

function buildIcav2WesPostRequestEventPattern(
  props: Icav2WesPostRequestTargetRuleEventPatternProps
) {
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

function buildIcav2AnalysisStateChangeRule(
  scope: Construct,
  props: BuildIcav2AnalysisStateChangeRuleProps
): Rule {
  return buildEventRule(scope, {
    ruleName: props.ruleName,
    eventPattern: buildIcav2AnalysisStateChangeEventPattern(props),
    eventBus: props.eventBus,
  });
}

function buildIcav2WesPostRequestRule(
  scope: Construct,
  props: buildIcav2WesPostRequestRuleProps
): Rule {
  return buildEventRule(scope, {
    ruleName: props.ruleName,
    eventPattern: buildIcav2WesPostRequestEventPattern(props),
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
      case 'icav2AnalysisStateChangeRule': {
        eventBridgeObjects.push({
          ruleName: eventBridgeRuleName,
          ruleObject: buildIcav2AnalysisStateChangeRule(scope, {
            ruleName: eventBridgeRuleName,
            eventBus: props.internalEventBus,
            icav2AnalysisStateChangeEventCode: props.icav2AnalysisStateChangeEventCode,
            icav2WesManagerTagKey: props.icav2WesManagerTagKey,
          }),
        });
        break;
      }
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
