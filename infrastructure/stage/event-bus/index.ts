import { BuildICAv2EventBusProps } from './interfaces';
import { IEventBus } from 'aws-cdk-lib/aws-events';
import * as events from 'aws-cdk-lib/aws-events';
import { Construct } from 'constructs';

export function buildICAv2WesEventBus(scope: Construct, props: BuildICAv2EventBusProps): IEventBus {
  return new events.EventBus(scope, props.eventBusName, props);
}
