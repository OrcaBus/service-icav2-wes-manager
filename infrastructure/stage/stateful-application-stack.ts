/*
Stateful Application Stack

This involves a few things,

1. The database to serve the API / Jobs
    Will need a global index on the 'name' field

2. The ICAv2 Event Pipe
3. The Internal Event Bus for the Event Pipe to publish to
*/

import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';

import { StatefulApplicationStackConfig } from './interfaces';
import {
  DEFAULT_DLQ_ALARM_THRESHOLD,
  DEFAULT_ICA_AWS_ACCOUNT_NUMBER,
  DEFAULT_ICA_QUEUE_VIZ_TIMEOUT,
  DEFAULT_ICA_SQS_NAME,
} from './constants';
import { createEventBridgePipe, getTopicArnFromTopicName } from './sqs';
import { buildICAv2WesDb, buildPayloadsTable } from './dynamodb';
import { buildICAv2WesEventBus } from './event-bus';
import { createArtefactsBucket } from './s3';

export type StatefulApplicationStackProps = StatefulApplicationStackConfig & cdk.StackProps;

// Stateful Application Stack
export class StatefulApplicationStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: StatefulApplicationStackProps) {
    super(scope, id, props);

    // Build the ICAv2 WES Event Bus
    const internalEventBusObject = buildICAv2WesEventBus(this, {
      eventBusName: props.internalEventBusName,
      eventBusDescription: props.internalEventBusDescription,
    });

    // Create the event pipe to join the ICA SQS queue to the event bus
    createEventBridgePipe(this, {
      icaEventPipeName: props.icav2EventPipeName,
      eventBusObj: internalEventBusObject,
      icaQueueName: DEFAULT_ICA_SQS_NAME,
      icaQueueVizTimeout: DEFAULT_ICA_QUEUE_VIZ_TIMEOUT,
      slackTopicArn: getTopicArnFromTopicName(props.slackTopicName),
      dlqMessageThreshold: DEFAULT_DLQ_ALARM_THRESHOLD,
      icaAwsAccountNumber: DEFAULT_ICA_AWS_ACCOUNT_NUMBER,
    });

    // Build the ICAv2 WES database
    buildICAv2WesDb(this, {
      tableName: props.tableName,
      indexNames: props.indexNames,
    });

    // Extra tables
    buildPayloadsTable(this, {
      tableName: props.payloadsTableName,
    });

    // Extra buckets
    createArtefactsBucket(this, props.payloadsBucketName);
  }
}
