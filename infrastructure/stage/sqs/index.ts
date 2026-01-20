import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import {
  IcaSqsEventPipeProps,
  IcaSqsQueueConstructProps,
  sfnEventPipeConstructProps,
  sqsEventPipeProps,
  SqsQueueConstructProps,
} from './interfaces';
import { Queue } from 'aws-cdk-lib/aws-sqs';
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
function createMonitoredQueue(scope: Construct, props: SqsQueueConstructProps): Queue {
  const mq = new MonitoredQueue(scope, props.queueName, {
    queueProps: {
      queueName: props.queueName,
      enforceSSL: true,
      visibilityTimeout: props.queueVizTimeout,
    },
    dlqProps: {
      queueName: props.queueName + '-dlq',
      enforceSSL: true,
      visibilityTimeout: props.queueVizTimeout,
    },
    messageThreshold: props.dlqMessageThreshold,
    topic: props.slackTopic,
  });

  return mq.queue;
}

function createExternalIcaMonitoredQueue(
  scope: Construct,
  props: IcaSqsQueueConstructProps
): Queue {
  const mq = createMonitoredQueue(scope, {
    queueName: props.queueName,
    slackTopic: props.slackTopic,
    dlqMessageThreshold: props.dlqMessageThreshold,
    queueVizTimeout: props.queueVizTimeout,
  });

  // Grant send message permissions to the ICA account
  mq.grantSendMessages(new iam.AccountPrincipal(props.icaAwsAccountNumber));

  return mq;
}

function createEventPipe(scope: Construct, props: sfnEventPipeConstructProps) {
  const targetInputTransformation = pipes.InputTransformation.fromObject({
    input: pipes.DynamicInput.fromEventPath('$.body'),
  });

  /* Get the step function object */
  const stepFunctionObject = sfn.StateMachine.fromStateMachineName(
    scope,
    props.stepFunctionName,
    `${STACK_PREFIX}--${props.stepFunctionName}`
  );

  // Inside your function:
  const logGroup = new LogGroup(scope, `${props.sqsQueue.queueName}--eventPipeLogGroup`);

  return new pipes.Pipe(scope, props.eventPipeName, {
    /* Source */
    source: new SqsSource(props.sqsQueue, {
      batchSize: 5,
      maximumBatchingWindow: Duration.seconds(10),
    }),
    /* Target */
    target: new SfnTarget(stepFunctionObject, {
      inputTransformation: targetInputTransformation,
    }),
    /*
      We only want to process messages where the array payload.tags.technicalTags contains an element
      that startswith "icav2_wes_orcabus_id="
   */
    filter: props.filters
      ? {
          filters: props.filters,
        }
      : undefined,
    logDestinations: [new pipes.CloudwatchLogsLogDestination(logGroup)],
  });
}

export function createLaunchIcaAnalysisEventBridgePipe(scope: Construct, props: sqsEventPipeProps) {
  /* Part 1 - Create the sqs queue */
  const monitoredQueue = createMonitoredQueue(scope, {
    queueName: props.queueName,
    slackTopic: props.slackTopic,
    queueVizTimeout: props.queueVizTimeout,
    dlqMessageThreshold: props.dlqMessageThreshold,
  });

  /* Part 2 - Create the event pipe */
  createEventPipe(scope, {
    eventPipeName: props.eventPipeName,
    sqsQueue: monitoredQueue,
    stepFunctionName: props.stepFunctionName,
  });
}

export function createExternalIcaEventBridgePipe(scope: Construct, props: IcaSqsEventPipeProps) {
  /* Part 1 - Create the sqs queue */
  const monitoredQueue = createExternalIcaMonitoredQueue(scope, {
    queueName: props.queueName,
    slackTopic: props.slackTopic,
    icaAwsAccountNumber: props.icaAwsAccountNumber,
    queueVizTimeout: props.queueVizTimeout,
    dlqMessageThreshold: props.dlqMessageThreshold,
  });

  /* Part 2 - Create the event pipe */
  createEventPipe(scope, {
    eventPipeName: props.eventPipeName,
    sqsQueue: monitoredQueue,
    stepFunctionName: props.stepFunctionName,
    filters: [
      {
        pattern: JSON.stringify({
          body: {
            payload: {
              tags: {
                technicalTags: [
                  {
                    prefix: 'icav2_wes_orcabus_id=',
                  },
                ],
              },
            },
          },
        }),
      },
    ],
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
