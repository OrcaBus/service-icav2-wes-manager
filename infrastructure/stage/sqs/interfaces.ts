import { Duration } from 'aws-cdk-lib';
import { Topic } from 'aws-cdk-lib/aws-sns';

export interface SqsQueueConstructProps {
  /* The ARN of the SNS Topic to receive DLQ notifications from CloudWatch */
  slackTopic: Topic;
  /* The CloudWatch Alarm threshold to use before raising an alarm */
  dlqMessageThreshold: number;
  /* The name for the incoming SQS queue (the DLQ with use this name with a "-dlq" postfix) */
  queueName: string;
  /* The visibility timeout for the queue */
  queueVizTimeout: Duration;
  /* For long polling */
  receiveMessageWaitTime?: Duration;
}

export interface IcaSqsQueueConstructProps extends SqsQueueConstructProps {
  /* The ICA account to grant publish permissions to */
  icaAwsAccountNumber: string;
}
