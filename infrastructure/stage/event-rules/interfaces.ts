import { EventPattern, IEventBus, Rule } from 'aws-cdk-lib/aws-events';

export type EventBridgeRuleName =
  // External rule - for requests to run analyses
  'icav2WesPostRequestRule';

export const eventBridgeRuleNameList: Array<EventBridgeRuleName> = ['icav2WesPostRequestRule'];

export interface Icav2WesPostRequestTargetRuleEventPatternProps {
  icav2WesRequestDetailType: string;
}

export interface EventBridgeRuleProps {
  ruleName: EventBridgeRuleName;
  eventBus: IEventBus;
  eventPattern: EventPattern;
}

export interface EventBridgeRuleObject {
  ruleName: EventBridgeRuleName;
  ruleObject: Rule;
  eventBus: IEventBus;
}

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
