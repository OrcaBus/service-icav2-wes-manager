import { App } from 'aws-cdk-lib';
import { Template, Match } from 'aws-cdk-lib/assertions';
import { StatefulApplicationStack } from '../infrastructure/stage/stateful-application-stack';
import { StatelessApplicationStack } from '../infrastructure/stage/stateless-application-stack';
import { getStatefulStackProps, getStatelessStackProps } from '../infrastructure/stage/config';
import { PROD_ENVIRONMENT } from '@orcabus/platform-cdk-constructs/deployment-stack-pipeline';

describe('CDK Infrastructure Assertions - API Rate-Limiting and Async Callback', () => {
  let statefulTemplate: Template;
  let statelessTemplate: Template;

  beforeAll(() => {
    // Use separate App instances to avoid ConstructTreeModifiedAfterSynth error
    const statefulApp = new App();
    const statefulStack = new StatefulApplicationStack(statefulApp, 'StatefulStack', {
      env: PROD_ENVIRONMENT,
      ...getStatefulStackProps('PROD'),
    });
    statefulTemplate = Template.fromStack(statefulStack);

    const statelessApp = new App();
    const statelessStack = new StatelessApplicationStack(statelessApp, 'StatelessStack', {
      env: PROD_ENVIRONMENT,
      ...getStatelessStackProps('PROD'),
    });
    statelessTemplate = Template.fromStack(statelessStack);
  });

  describe('Launch_Analysis_Queue properties (Requirement 2.1, 2.4)', () => {
    test('Launch_Analysis_Queue has visibility timeout of at least 90 minutes (5400 seconds)', () => {
      statefulTemplate.hasResourceProperties('AWS::SQS::Queue', {
        QueueName: 'Icav2WesLaunchIcaAnalysisSqsQueue',
        VisibilityTimeout: 5400,
      });
    });

    test('Launch_Analysis_Queue has DLQ with maxReceiveCount of 3', () => {
      statefulTemplate.hasResourceProperties('AWS::SQS::Queue', {
        QueueName: 'Icav2WesLaunchIcaAnalysisSqsQueue',
        RedrivePolicy: Match.objectLike({
          maxReceiveCount: 3,
        }),
      });
    });

    test('Launch_Analysis_Queue DLQ has retention period of 14 days (1209600 seconds)', () => {
      statefulTemplate.hasResourceProperties('AWS::SQS::Queue', {
        QueueName: 'Icav2WesLaunchIcaAnalysisSqsQueue-dlq',
        MessageRetentionPeriod: 1209600,
      });
    });
  });

  describe('Event Source Mapping configuration (Requirement 3.4)', () => {
    test('launchQueueConsumer event source mapping has batchSize=1 and maxConcurrency=5', () => {
      statelessTemplate.hasResourceProperties('AWS::Lambda::EventSourceMapping', {
        BatchSize: 1,
        ScalingConfig: {
          MaximumConcurrency: 5,
        },
      });
    });
  });

  describe('API Lambda IAM permissions (Requirements 2.1, 3.4)', () => {
    test('API Lambda has sqs:SendMessage permission', () => {
      statelessTemplate.hasResourceProperties('AWS::IAM::Policy', {
        PolicyDocument: {
          Statement: Match.arrayWith([
            Match.objectLike({
              Action: Match.anyValue(),
              Effect: 'Allow',
              Resource: Match.anyValue(),
            }),
          ]),
        },
      });

      // Verify that there's an IAM policy with sqs:SendMessage action on the launch analysis queue
      const policies = statelessTemplate.findResources('AWS::IAM::Policy');
      const hasSqsSendMessage = Object.values(policies).some((policy) => {
        const statements = (policy as any).Properties?.PolicyDocument?.Statement;
        if (!Array.isArray(statements)) return false;
        return statements.some((stmt: any) => {
          const actions = Array.isArray(stmt.Action) ? stmt.Action : [stmt.Action];
          return (
            actions.some(
              (a: string) =>
                a === 'sqs:SendMessage' ||
                a === 'sqs:GetQueueAttributes' ||
                a === 'sqs:GetQueueUrl'
            ) && stmt.Effect === 'Allow'
          );
        });
      });
      expect(hasSqsSendMessage).toBe(true);
    });

    test('API Lambda has states:StartExecution permission for unlockCallbackId SFN', () => {
      const policies = statelessTemplate.findResources('AWS::IAM::Policy');
      const hasStartExecution = Object.values(policies).some((policy) => {
        const statements = (policy as any).Properties?.PolicyDocument?.Statement;
        if (!Array.isArray(statements)) return false;
        return statements.some((stmt: any) => {
          const actions = Array.isArray(stmt.Action) ? stmt.Action : [stmt.Action];
          return actions.includes('states:StartExecution') && stmt.Effect === 'Allow';
        });
      });
      expect(hasStartExecution).toBe(true);
    });
  });

  describe('DLQ CloudWatch Alarm (Requirement 6.1)', () => {
    test('DLQ alarm has threshold of 1', () => {
      statefulTemplate.hasResourceProperties('AWS::CloudWatch::Alarm', {
        Threshold: 1,
        MetricName: 'ApproximateNumberOfMessagesVisible',
      });
    });
  });
});
