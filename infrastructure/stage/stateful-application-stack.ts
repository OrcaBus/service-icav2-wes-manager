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
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import { AttributeType } from 'aws-cdk-lib/aws-dynamodb';
import * as events from 'aws-cdk-lib/aws-events';
import * as pipes from '@aws-cdk/aws-pipes-alpha';
import * as iam from 'aws-cdk-lib/aws-iam';
import { MonitoredQueue } from 'sqs-dlq-monitoring';

import {
  BuildICAv2EventBusProps,
  BuildICAv2WesDbProps,
  StatefulApplicationStackConfig,
  IcaEventPipeConstructProps,
  IcaSqsEventPipeProps,
  IcaSqsQueueConstructProps,
} from './interfaces';
import {
  DEFAULT_DLQ_ALARM_THRESHOLD,
  DEFAULT_ICA_AWS_ACCOUNT_NUMBER,
  DEFAULT_ICA_QUEUE_VIZ_TIMEOUT,
  DEFAULT_ICA_SQS_NAME,
  TABLE_REMOVAL_POLICY,
} from './constants';
import { GlobalSecondaryIndexPropsV2 } from 'aws-cdk-lib/aws-dynamodb/lib/table-v2';
import { IEventBus } from 'aws-cdk-lib/aws-events';
import { SqsSource } from '@aws-cdk/aws-pipes-sources-alpha';
import { Queue } from 'aws-cdk-lib/aws-sqs';
import { Topic } from 'aws-cdk-lib/aws-sns';

export type StatefulApplicationStackProps = StatefulApplicationStackConfig & cdk.StackProps;

// Stateful Application Stack
export class StatefulApplicationStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: StatefulApplicationStackProps) {
    super(scope, id, props);

    // Build the ICAv2 WES Event Bus
    const internalEventBusObject = this.buildICAv2WesEventBus({
      eventBusName: props.internalEventBusName,
      eventBusDescription: props.internalEventBusDescription,
    });

    // Create the event pipe to join the ICA SQS queue to the event bus
    this.createEventBridgePipe({
      icaEventPipeName: props.icav2EventPipeName,
      eventBusObj: internalEventBusObject,
      icaQueueName: DEFAULT_ICA_SQS_NAME,
      icaQueueVizTimeout: DEFAULT_ICA_QUEUE_VIZ_TIMEOUT,
      slackTopicArn: this.getTopicArnFromTopicName(props.slackTopicName),
      dlqMessageThreshold: DEFAULT_DLQ_ALARM_THRESHOLD,
      icaAwsAccountNumber: DEFAULT_ICA_AWS_ACCOUNT_NUMBER,
    });

    // Build the ICAv2 WES database
    this.buildICAv2WesDb({
      tableName: props.tableName,
      indexNames: props.indexNames,
    });
  }

  private buildICAv2WesEventBus(props: BuildICAv2EventBusProps): IEventBus {
    return new events.EventBus(this, props.eventBusName, props);
  }

  // Get the topic ARN from the topic name
  private getTopicArnFromTopicName(topicName: string): string {
    return `arn:aws:sns:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:${topicName}`;
  }

  // Create the INPUT SQS queue that will receive the ICA events
  // This should have a DLQ and be monitored via CloudWatch alarm and Slack notifications
  private createMonitoredQueue(props: IcaSqsQueueConstructProps): Queue {
    // Note: the construct MonitoredQueue demands a "Topic" construct as it usually modifies the topic adding subscriptions.
    // However, our use case, as we don't add any additional subscriptions, does not require topic modification, so we can pass on an "ITopic" as "Topic".
    const topic: Topic = Topic.fromTopicArn(this, 'SlackTopic', props.slackTopicArn) as Topic;

    const mq = new MonitoredQueue(this, props.icaQueueName, {
      queueProps: {
        queueName: props.icaQueueName,
        enforceSSL: true,
        visibilityTimeout: props.icaQueueVizTimeout,
      },
      dlqProps: {
        queueName: props.icaQueueName + '-dlq',
        enforceSSL: true,
        visibilityTimeout: props.icaQueueVizTimeout,
      },
      messageThreshold: props.dlqMessageThreshold,
      topic: topic,
    });
    mq.queue.grantSendMessages(new iam.AccountPrincipal(props.icaAwsAccountNumber));

    return mq.queue;
  }

  private createEventPipe(props: IcaEventPipeConstructProps) {
    const targetInputTransformation = pipes.InputTransformation.fromObject({
      'ica-event': pipes.DynamicInput.fromEventPath('$.body'),
    });

    return new pipes.Pipe(this, props.icaEventPipeName, {
      source: new SqsSource(props.icaSqsQueue),
      target: new EventBusTarget(props.eventBusObj, {
        inputTransformation: targetInputTransformation,
      }),
    });
  }

  private createEventBridgePipe(props: IcaSqsEventPipeProps) {
    /* Part 1 - Create the monitored queue */
    const monitoredQueue = this.createMonitoredQueue({
      icaQueueName: props.icaQueueName,
      slackTopicArn: props.slackTopicArn,
      icaAwsAccountNumber: props.icaAwsAccountNumber,
      icaQueueVizTimeout: props.icaQueueVizTimeout,
      dlqMessageThreshold: props.dlqMessageThreshold,
    });

    /* Part 2 - Create the event pipe */
    this.createEventPipe({
      icaEventPipeName: props.icaEventPipeName,
      icaSqsQueue: monitoredQueue,
      eventBusObj: props.eventBusObj,
    });
  }

  private buildICAv2WesDb(props: BuildICAv2WesDbProps) {
    /*
        First generate the global secondary index for the 'name' field
        Hopefully this construct will be useful for other projects as well
        */
    const globalSecondaryIndexes: GlobalSecondaryIndexPropsV2[] = [];
    for (const indexName of props.indexNames) {
      globalSecondaryIndexes.push({
        indexName: `${indexName}-index`,
        partitionKey: {
          name: indexName,
          type: AttributeType.STRING,
        },
        sortKey: {
          name: 'id',
          type: AttributeType.STRING,
        },
      });
    }

    new dynamodb.TableV2(this, props.tableName, {
      partitionKey: {
        name: 'id',
        type: AttributeType.STRING,
      },
      tableName: props.tableName,
      removalPolicy: TABLE_REMOVAL_POLICY,
      pointInTimeRecoverySpecification: {
        pointInTimeRecoveryEnabled: true,
      },
      timeToLiveAttribute: 'ttl',
      globalSecondaryIndexes: globalSecondaryIndexes,
    });
  }
}

// Creates a pipe TARGET wrapping an EventBus
class EventBusTarget implements pipes.ITarget {
  // No official EventBusTarget implementations exist (yet). This is following recommendations from:
  // https://constructs.dev/packages/@aws-cdk/aws-pipes-alpha/v/2.133.0-alpha.0?lang=typescript#example-target-implementation
  targetArn: string;
  private inputTransformation: pipes.IInputTransformation | undefined;

  constructor(
    private readonly eventBus: IEventBus,
    props: { inputTransformation?: pipes.IInputTransformation } = {}
  ) {
    this.eventBus = eventBus;
    this.targetArn = eventBus.eventBusArn;
    this.inputTransformation = props?.inputTransformation;
  }

  bind(_pipe: pipes.Pipe): pipes.TargetConfig {
    return {
      targetParameters: {
        inputTemplate: this.inputTransformation?.bind(_pipe).inputTemplate,
      },
    };
  }

  grantPush(pipeRole: iam.IRole): void {
    this.eventBus.grantPutEventsTo(pipeRole);
  }
}
