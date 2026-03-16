import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { IcaSqsQueueConstructProps, SqsQueueConstructProps } from './interfaces';
import { Queue } from 'aws-cdk-lib/aws-sqs';
import { MonitoredQueue } from 'sqs-dlq-monitoring';
import * as iam from 'aws-cdk-lib/aws-iam';

export function getTopicArnFromTopicName(topicName: string): string {
  return `arn:aws:sns:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:${topicName}`;
}

// Create the INPUT SQS queue that will receive the ICA events
// This should have a DLQ and be monitored via CloudWatch alarm and Slack notifications
export function createMonitoredQueue(scope: Construct, props: SqsQueueConstructProps): Queue {
  const mq = new MonitoredQueue(scope, props.queueName, {
    queueProps: {
      queueName: props.queueName,
      enforceSSL: true,
      visibilityTimeout: props.queueVizTimeout,
      receiveMessageWaitTime: props.receiveMessageWaitTime,
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

export function createExternalIcaMonitoredQueue(
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
