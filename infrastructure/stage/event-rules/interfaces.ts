import { EventPattern, IEventBus, Rule } from 'aws-cdk-lib/aws-events';

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
