/*
Stateful Application Stack

This involves a few things,

1. The database to serve the API / Jobs
    Will need a global index on the 'name' field

2. The ICAv2 Event Pipe
3. The Internal Event Bus for the Event Pipe to publish to
*/

import * as cdk from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Effect } from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

import { StatefulApplicationStackConfig } from './interfaces';
import {
  DEFAULT_ICA_AWS_ACCOUNT_NUMBER,
  DEFAULT_ICA_STATE_CHANGE_MAX_TIMEOUT,
  DEFAULT_WES_REQUEST_QUEUE_TIMEOUT,
} from './constants';
import {
  createExternalIcaMonitoredQueue,
  createMonitoredQueue,
  getTopicArnFromTopicName,
} from './sqs';
import { buildCallbackTable, buildICAv2WesDb, buildPayloadsTable } from './dynamodb';
import { createArtefactsBucket } from './s3';
import { buildSchemas } from './event-schemas';
import { Topic } from 'aws-cdk-lib/aws-sns';
import { Duration } from 'aws-cdk-lib';
import { EventBus } from 'aws-cdk-lib/aws-events';

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

    const eventBus = EventBus.fromEventBusName(
      this,
      props.externalEventBusName,
      props.externalEventBusName
    );

    // Buffer to launch ICA analysis requests
    const icav2WesRequestQueue = createMonitoredQueue(this, {
      dlqMessageThreshold: 1,
      queueName: props.icav2WesRequestSqsQueueName,
      queueVizTimeout: DEFAULT_WES_REQUEST_QUEUE_TIMEOUT,
      slackTopic: slackTopic,
      receiveMessageWaitTime: Duration.seconds(20),
    });

    // From https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-use-resource-based.html#sqs-permissions
    // In order to allow EventBridge to send messages to your SQS queue, you must add a resource-based policy to the queue.
    icav2WesRequestQueue.addToResourcePolicy(
      new iam.PolicyStatement({
        effect: Effect.ALLOW,
        principals: [new iam.ServicePrincipal('events.amazonaws.com')],
        actions: ['sqs:SendMessage'],
        resources: [icav2WesRequestQueue.queueArn],
        conditions: {
          ArnEquals: {
            'aws:SourceArn': `arn:aws:events:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:rule/${eventBus.eventBusName}/${props.icav2WesRequestEventRuleName}`,
          },
        },
      })
    );

    // Buffer to handle ICA state change requests
    createExternalIcaMonitoredQueue(this, {
      queueName: props.icaExternalSqsQueueName,
      slackTopic: slackTopic,
      icaAwsAccountNumber: DEFAULT_ICA_AWS_ACCOUNT_NUMBER,
      queueVizTimeout: DEFAULT_ICA_STATE_CHANGE_MAX_TIMEOUT,
      dlqMessageThreshold: 1,
    });

    // // Build the ICAv2 WES database
    buildICAv2WesDb(this, {
      tableName: props.wesTableName,
      indexNames: props.indexNames,
    });

    // Extra tables
    buildPayloadsTable(this, {
      tableName: props.payloadsTableName,
    });

    buildCallbackTable(this, {
      tableName: props.callbackTableName,
    });

    // Extra buckets
    createArtefactsBucket(this, props.payloadsBucketName);

    // Create schemas
    buildSchemas(this);
  }
}
