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
import * as sfn from 'aws-cdk-lib/aws-stepfunctions';
import { Duration } from 'aws-cdk-lib';
import { IStateMachine } from 'aws-cdk-lib/aws-stepfunctions';
import { STACK_PREFIX } from '../constants';
import { LogGroup } from 'aws-cdk-lib/aws-logs';

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
    input: pipes.DynamicInput.fromEventPath('$.body'),
  });

  /* Get the step function object */
  const stepFunctionObject = sfn.StateMachine.fromStateMachineName(
    scope,
    'handleIcaEventSfn',
    `${STACK_PREFIX}--${props.stepFunctionName}`
  );

  // Inside your function:
  const logGroup = new LogGroup(scope, 'IcaEventPipeLogGroup');

  return new pipes.Pipe(scope, props.icaEventPipeName, {
    source: new SqsSource(props.icaSqsQueue, {
      batchSize: 5,
      maximumBatchingWindow: Duration.seconds(10),
    }),
    target: new SfnTarget(stepFunctionObject, {
      inputTransformation: targetInputTransformation,
    }),
    logDestinations: [new pipes.CloudwatchLogsLogDestination(logGroup)],
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
    stepFunctionName: props.stepFunctionName,
  });
}

// Creates a pipe TARGET wrapping into a Step Functions
class SfnTarget implements pipes.ITarget {
  targetArn: string;
  private inputTransformation: pipes.IInputTransformation | undefined;

  constructor(
    private readonly stepFunctionObject: IStateMachine,
    props: { inputTransformation?: pipes.IInputTransformation } = {}
  ) {
    this.stepFunctionObject = stepFunctionObject;
    this.targetArn = stepFunctionObject.stateMachineArn;
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
    this.stepFunctionObject.grantStartSyncExecution(pipeRole);
  }
}
