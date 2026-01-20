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
  DEFAULT_QUEUE_TIMEOUT,
} from './constants';
import {
  createExternalIcaEventBridgePipe,
  createLaunchIcaAnalysisEventBridgePipe,
  getTopicArnFromTopicName,
} from './sqs';
import { buildICAv2WesDb, buildPayloadsTable } from './dynamodb';
import { createArtefactsBucket } from './s3';
import { buildSchemas } from './event-schemas';
import { Topic } from 'aws-cdk-lib/aws-sns';

export type StatefulApplicationStackProps = StatefulApplicationStackConfig & cdk.StackProps;

// Stateful Application Stack
export class StatefulApplicationStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: StatefulApplicationStackProps) {
    super(scope, id, props);
    // Slack topic ARN
    // However, our use case, as we don't add any additional subscriptions, does not require topic modification, so we can pass on an "ITopic" as "Topic".
    const slackTopic: Topic = Topic.fromTopicArn(
      this,
      'SlackTopic',
      getTopicArnFromTopicName(props.slackTopicName)
    ) as Topic;

    // Create the launch sqs queue to stagger launch requests to ICA
    createLaunchIcaAnalysisEventBridgePipe(this, {
      eventPipeName: props.launchIcaAnalysisEventPipeName,
      stepFunctionName: 'launchIcav2Analysis',
      queueName: props.launchIcaAnalysisSqsQueueName,
      queueVizTimeout: DEFAULT_QUEUE_TIMEOUT,
      slackTopic: slackTopic,
      dlqMessageThreshold: 1,
    });

    // Create the event pipe to join the ICA SQS queue to the event bus
    createExternalIcaEventBridgePipe(this, {
      eventPipeName: props.icaExternalEventPipeName,
      stepFunctionName: 'handleIcav2AnalysisStateChange',
      queueName: props.icaExternalSqsQueueName,
      queueVizTimeout: DEFAULT_QUEUE_TIMEOUT,
      slackTopic: slackTopic,
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

    // Create schemas
    buildSchemas(this);
  }
}
