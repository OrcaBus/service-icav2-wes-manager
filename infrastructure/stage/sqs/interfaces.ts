import { Duration } from 'aws-cdk-lib';
import { Queue } from 'aws-cdk-lib/aws-sqs';
import { IEventBus } from 'aws-cdk-lib/aws-events';

export interface IcaSqsQueueConstructProps {
  /* The name for the incoming SQS queue (the DLQ with use this name with a "-dlq" postfix) */
  icaQueueName: string;
  /* The visibility timeout for the queue */
  icaQueueVizTimeout: Duration;
  /* The ARN of the SNS Topic to receive DLQ notifications from CloudWatch */
  slackTopicArn: string;
  /* The CloudWatch Alarm threshold to use before raising an alarm */
  dlqMessageThreshold: number;
  /* The ICA account to grant publish permissions to */
  icaAwsAccountNumber: string;
}

export interface IcaEventPipeConstructProps {
  /* The Sqs object */
  icaSqsQueue: Queue;
  /* The name for the Event Pipe */
  icaEventPipeName: string;
  /* The Event Bus to forward events to (used to lookup the Event Bus) */
  eventBusObj: IEventBus;
}

export type IcaSqsEventPipeProps = Omit<IcaEventPipeConstructProps, 'icaSqsQueue'> &
  IcaSqsQueueConstructProps;
