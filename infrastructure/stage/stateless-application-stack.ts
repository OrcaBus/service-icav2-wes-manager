// Standard cdk imports
import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as events from 'aws-cdk-lib/aws-events';

// Application imports
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as ssm from 'aws-cdk-lib/aws-ssm';

// Local imports
import { StatelessApplicationStackConfig } from './interfaces';
import { NagSuppressions } from 'cdk-nag';
import { StageName } from '@orcabus/platform-cdk-constructs/shared-config/accounts';
import { buildAllLambdas } from './lambda';
import { buildAllStepFunctions } from './step-functions';
import { buildEventBridgeRules } from './event-rules';
import { buildAllEventBridgeTargets } from './event-targets';
import {
  addHttpRoutes,
  buildApiGateway,
  buildApiIntegration,
  buildApiInterfaceLambda,
} from './api';

export type StatelessApplicationStackProps = StatelessApplicationStackConfig & cdk.StackProps;

// Stateless Application Stack
export class StatelessApplicationStack extends cdk.Stack {
  public readonly stageName: StageName;
  constructor(scope: Construct, id: string, props: StatelessApplicationStackProps) {
    super(scope, id, props);
    this.stageName = props.stageName;

    // Get dynamodb table (built in the stateful stack)
    const dynamodbTable = dynamodb.TableV2.fromTableName(this, props.tableName, props.tableName);

    // Get the event bus objects
    const externalEventBusObject = events.EventBus.fromEventBusName(
      this,
      props.externalEventBusName,
      props.externalEventBusName
    );
    const internalEventBusObject = events.EventBus.fromEventBusName(
      this,
      props.internalEventBusName,
      props.internalEventBusName
    );

    const hostedZoneSsmParameterObj = ssm.StringParameter.fromStringParameterName(
      this,
      props.hostedZoneSsmParameterName,
      props.hostedZoneSsmParameterName
    );

    // Build the lambdas
    const lambdaObjects = buildAllLambdas(this);

    // Build the step functions
    const stepFunctionObjects = buildAllStepFunctions(this, {
      lambdaFunctions: lambdaObjects,
      eventBus: externalEventBusObject,
      eventSource: props.eventSource,
      icav2DataCopySyncDetail: props.icav2DataCopySyncDetailType,
    });

    // Build event bridge rules
    const eventBridgeRuleObjects = buildEventBridgeRules(this, {
      /* Event buses */
      internalEventBus: internalEventBusObject,
      externalEventBus: externalEventBusObject,

      /* Event constants */
      icav2AnalysisStateChangeEventCode: props.icav2AnalysisStateChangeEventCode,
      icav2WesManagerTagKey: props.icav2WesManagerTagKey,
      icav2WesRequestDetailType: props.icav2WesRequestDetailType,
    });

    // Add the event-bridge rules
    buildAllEventBridgeTargets({
      eventBridgeRuleObjects: eventBridgeRuleObjects,
      stepFunctionObjects: stepFunctionObjects,
      lambdaObjects: lambdaObjects,
    });

    // Build the API interface lambda
    const lambdaApi = buildApiInterfaceLambda(this, {
      /* Lambda props */
      lambdaName: 'icav2WesApiInterface',

      /* Table props */
      table: dynamodbTable,
      tableIndexNames: props.indexNames,

      /* Step functions triggered by the API */
      stepFunctions: stepFunctionObjects.filter((stepFunctionObject) =>
        ['launchIcav2Analysis', 'abortIcav2Analysis'].includes(stepFunctionObject.stateMachineName)
      ),

      /* Event bus */
      eventBus: externalEventBusObject,
      eventSource: props.eventSource,
      icav2WesAnalysisStateChangeEventDetail: props.icav2WesAnalysisStateChangeDetailType,

      /* SSM and Secrets */
      hostedZoneSsmParameter: hostedZoneSsmParameterObj,
    });

    // Build the API Gateway
    const apiGateway = buildApiGateway(this, props.apiGatewayCognitoProps);
    const apiIntegration = buildApiIntegration({
      lambdaFunction: lambdaApi,
    });
    addHttpRoutes(this, {
      apiGateway: apiGateway,
      apiIntegration: apiIntegration,
    });

    // Add in stack suppressions
    NagSuppressions.addStackSuppressions(this, [
      {
        id: 'AwsSolutions-IAM4',
        reason: 'We need to add this for the lambdas to work',
      },
    ]);
  }
}
