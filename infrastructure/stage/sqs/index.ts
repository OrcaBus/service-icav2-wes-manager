import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import {
  IcaEventPipeConstructProps,
  IcaSqsEventPipeProps,
  IcaSqsQueueConstructProps,
} from './interfaces';
import { Queue } from 'aws-cdk-lib/aws-sqs';
import { Topic } from 'aws-cdk-lib/aws-sns';
import { MonitoredQueue } from 'sqs-dlq-monitoring';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as pipes from '@aws-cdk/aws-pipes-alpha';
import { SqsSource } from '@aws-cdk/aws-pipes-sources-alpha';
import { IEventBus } from 'aws-cdk-lib/aws-events';

export function getTopicArnFromTopicName(topicName: string): string {
  return `arn:aws:sns:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:${topicName}`;
}

// Create the INPUT SQS queue that will receive the ICA events
// This should have a DLQ and be monitored via CloudWatch alarm and Slack notifications
function createMonitoredQueue(scope: Construct, props: IcaSqsQueueConstructProps): Queue {
  // Note: the construct MonitoredQueue demands a "Topic" construct as it usually modifies the topic adding subscriptions.
  // However, our use case, as we don't add any additional subscriptions, does not require topic modification, so we can pass on an "ITopic" as "Topic".
  const topic: Topic = Topic.fromTopicArn(scope, 'SlackTopic', props.slackTopicArn) as Topic;

  const mq = new MonitoredQueue(scope, props.icaQueueName, {
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

function createEventPipe(scope: Construct, props: IcaEventPipeConstructProps) {
  const targetInputTransformation = pipes.InputTransformation.fromObject({
    'ica-event': pipes.DynamicInput.fromEventPath('$.body'),
  });

  return new pipes.Pipe(scope, props.icaEventPipeName, {
    source: new SqsSource(props.icaSqsQueue),
    target: new EventBusTarget(props.eventBusObj, {
      inputTransformation: targetInputTransformation,
    }),
  });
}

export function createEventBridgePipe(scope: Construct, props: IcaSqsEventPipeProps) {
  /* Part 1 - Create the monitored  */
  const monitoredQueue = createMonitoredQueue(scope, {
    icaQueueName: props.icaQueueName,
    slackTopicArn: props.slackTopicArn,
    icaAwsAccountNumber: props.icaAwsAccountNumber,
    icaQueueVizTimeout: props.icaQueueVizTimeout,
    dlqMessageThreshold: props.dlqMessageThreshold,
  });

  /* Part 2 - Create the event pipe */
  createEventPipe(scope, {
    icaEventPipeName: props.icaEventPipeName,
    icaSqsQueue: monitoredQueue,
    eventBusObj: props.eventBusObj,
  });
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
