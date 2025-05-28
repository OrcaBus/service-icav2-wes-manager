// Standard cdk imports
import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as events from 'aws-cdk-lib/aws-events';
import * as sfn from 'aws-cdk-lib/aws-stepfunctions';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as eventsTargets from 'aws-cdk-lib/aws-events-targets';
import { Rule } from 'aws-cdk-lib/aws-events';
import { HttpMethod } from 'aws-cdk-lib/aws-apigatewayv2';

// Application imports
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';

// Local imports
import {
  BuildLambdaProps,
  SfnProps,
  EventBridgeRuleObject,
  EventBridgeRuleProps,
  lambdaNameList,
  LambdaObject,
  lambdaToRequirementsMap,
  sfnNameList,
  SfnObjectProps,
  StatelessApplicationStackConfig,
  sfnToRequirementsMap,
  stepFunctionToLambdaMap,
  BuildSfnsProps,
  Icav2AnalysisStateChangeRuleEventPatternProps,
  Icav2WesPostRequestTargetRuleEventPatternProps,
  BuildIcav2AnalysisStateChangeRuleProps,
  buildIcav2WesPostRequestRuleProps,
  BuildEventBridgeRulesProps,
  eventBridgeRuleNameList,
  eventBridgeTargetsNameList,
  AddSfnAsEventBridgeTargetProps,
  AddLambdaAsEventBridgeTargetProps,
  EventBridgeTargetsProps,
  LambdaApiProps,
  BuildApiIntegrationProps,
  BuildHttpRoutesProps,
} from './interfaces';
import path from 'path';
import { Duration } from 'aws-cdk-lib';
import { API_VERSION, INTERFACE_DIR, LAMBDA_DIR, STEP_FUNCTIONS_DIR } from './constants';
import { NagSuppressions } from 'cdk-nag';
import { PythonUvFunction } from '@orcabus/platform-cdk-constructs/lambda';
import { EventPattern } from 'aws-cdk-lib/aws-events/lib/event-pattern';
import {
  OrcaBusApiGateway,
  OrcaBusApiGatewayProps,
} from '@orcabus/platform-cdk-constructs/api-gateway';
import { HttpLambdaIntegration } from 'aws-cdk-lib/aws-apigatewayv2-integrations';
import { HttpNoneAuthorizer, HttpRoute, HttpRouteKey } from 'aws-cdk-lib/aws-apigatewayv2';

export type StatelessApplicationStackProps = StatelessApplicationStackConfig & cdk.StackProps;

// Stateless Application Stack
export class StatelessApplicationStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: StatelessApplicationStackProps) {
    super(scope, id, props);

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

    // Build the lambdas
    const lambdaObjects = this.buildAllLambdas();

    // Build the step functions
    const stepFunctionObjects = this.buildAllStepFunctions({
      lambdaFunctions: lambdaObjects,
      eventBus: externalEventBusObject,
      eventSource: props.eventSource,
      icav2DataCopySyncDetail: props.icav2DataCopySyncDetailType,
    });

    // Build event bridge rules
    const eventBridgeRuleObjects = this.buildEventBridgeRules({
      /* Event buses */
      internalEventBus: internalEventBusObject,
      externalEventBus: externalEventBusObject,

      /* Event constants */
      icav2AnalysisStateChangeEventCode: props.icav2AnalysisStateChangeEventCode,
      icav2WesManagerTagKey: props.icav2WesManagerTagKey,
      icav2WesRequestDetailType: props.icav2WesRequestDetailType,
    });

    // Add the event-bridge rules
    this.buildAllEventBridgeTargets({
      eventBridgeRuleObjects: eventBridgeRuleObjects,
      stepFunctionObjects: stepFunctionObjects,
      lambdaObjects: lambdaObjects,
    });

    // Build the API interface lambda
    const lambdaApi = this.buildApiInterfaceLambda({
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
    });

    // Build the API Gateway
    const apiGateway = this.buildApiGateway(props.apiGatewayCognitoProps);
    const apiIntegration = this.buildApiIntegration({
      lambdaFunction: lambdaApi,
    });
    this.addHttpRoutes({
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

  /* Lambda stuff */
  private buildAllLambdas(): LambdaObject[] {
    // Iterate over lambdaLayerToMapping and create the lambda functions
    const lambdaObjects: LambdaObject[] = [];
    for (const lambdaName of lambdaNameList) {
      lambdaObjects.push(
        this.buildLambda({
          lambdaName: lambdaName,
        })
      );
    }

    return lambdaObjects;
  }

  /** Lambda stuff */
  private buildLambda(props: BuildLambdaProps): LambdaObject {
    const lambdaNameToSnakeCase = this.camelCaseToSnakeCase(props.lambdaName);

    // Create the lambda function
    const lambdaFunction = new PythonUvFunction(this, props.lambdaName, {
      entry: path.join(LAMBDA_DIR, lambdaNameToSnakeCase + '_py'),
      runtime: lambda.Runtime.PYTHON_3_12,
      architecture: lambda.Architecture.ARM_64,
      index: lambdaNameToSnakeCase + '.py',
      handler: 'handler',
      timeout: Duration.seconds(60),
      memorySize: 2048,
      includeIcav2Layer: lambdaToRequirementsMap[props.lambdaName].needsIcav2ToolkitLayer,
      includeOrcabusApiToolsLayer:
        lambdaToRequirementsMap[props.lambdaName].needsOrcabusTookitLayer,
    });

    // AwsSolutions-L1 - We'll migrate to PYTHON_3_13 ASAP, soz
    // AwsSolutions-IAM4 - We need to add this for the lambda to work
    NagSuppressions.addResourceSuppressions(
      lambdaFunction,
      [
        {
          id: 'AwsSolutions-L1',
          reason: 'Will migrate to PYTHON_3_13 ASAP, soz',
        },
      ],
      true
    );

    /* Return the function */
    return {
      lambdaName: props.lambdaName,
      lambdaFunction: lambdaFunction,
    };
  }

  /** Step Function stuff */
  private createStateMachineDefinitionSubstitutions(props: SfnProps): {
    [key: string]: string;
  } {
    const definitionSubstitutions: { [key: string]: string } = {};

    const sfnRequirements = sfnToRequirementsMap[props.stateMachineName];
    const lambdaFunctionNamesInSfn = stepFunctionToLambdaMap[props.stateMachineName];
    const lambdaFunctions = props.lambdaFunctions.filter((lambdaObject) =>
      lambdaFunctionNamesInSfn.includes(lambdaObject.lambdaName)
    );

    /* Substitute lambdas in the state machine definition */
    for (const lambdaObject of lambdaFunctions) {
      const sfnSubtitutionKey = `__${this.camelCaseToSnakeCase(lambdaObject.lambdaName)}_lambda_function_arn__`;
      definitionSubstitutions[sfnSubtitutionKey] =
        lambdaObject.lambdaFunction.currentVersion.functionArn;
    }

    /* Sfn Requirements */
    if (sfnRequirements.needsExternalEventBusPutPermissions) {
      definitionSubstitutions['__external_event_bus_name__'] = props.eventBus.eventBusName;
      definitionSubstitutions['__icav2_data_copy_sync_detail_type__'] =
        props.icav2DataCopySyncDetail;
      definitionSubstitutions['__stack_source__'] = props.eventSource;
    }

    return definitionSubstitutions;
  }

  private wireUpStateMachinePermissions(props: SfnObjectProps): void {
    /* Wire up lambda permissions */
    const sfnRequirements = sfnToRequirementsMap[props.stateMachineName];

    const lambdaFunctionNamesInSfn = stepFunctionToLambdaMap[props.stateMachineName];
    const lambdaFunctions = props.lambdaFunctions.filter((lambdaObject) =>
      lambdaFunctionNamesInSfn.includes(lambdaObject.lambdaName)
    );

    if (sfnRequirements.needsExternalEventBusPutPermissions) {
      props.eventBus.grantPutEventsTo(props.stateMachineObj);
    }

    /* Allow the state machine to invoke the lambda function */
    for (const lambdaObject of lambdaFunctions) {
      lambdaObject.lambdaFunction.currentVersion.grantInvoke(props.stateMachineObj);
    }
  }

  private buildStepFunction(props: SfnProps): SfnObjectProps {
    const sfnNameToSnakeCase = this.camelCaseToSnakeCase(props.stateMachineName);

    /* Create the state machine definition substitutions */
    const stateMachine = new sfn.StateMachine(this, props.stateMachineName, {
      stateMachineName: `icav2-wes-${props.stateMachineName}`,
      definitionBody: sfn.DefinitionBody.fromFile(
        path.join(STEP_FUNCTIONS_DIR, sfnNameToSnakeCase + `_sfn_template.asl.json`)
      ),
      definitionSubstitutions: this.createStateMachineDefinitionSubstitutions(props),
    });

    /* Grant the state machine permissions */
    this.wireUpStateMachinePermissions({
      stateMachineObj: stateMachine,
      ...props,
    });

    /* Nag Suppressions */
    /* AwsSolutions-SF1 - We don't need ALL events to be logged */
    /* AwsSolutions-SF2 - We also don't need X-Ray tracing */
    NagSuppressions.addResourceSuppressions(
      stateMachine,
      [
        {
          id: 'AwsSolutions-SF1',
          reason: 'We do not need all events to be logged',
        },
        {
          id: 'AwsSolutions-SF2',
          reason: 'We do not need X-Ray tracing',
        },
      ],
      true
    );

    /* Return as a state machine object property */
    return {
      ...props,
      stateMachineObj: stateMachine,
    };
  }

  private buildAllStepFunctions(props: BuildSfnsProps): SfnObjectProps[] {
    // Initialize the step function objects
    const sfnObjects = [] as SfnObjectProps[];

    // Iterate over lambdaLayerToMapping and create the lambda functions
    for (const sfnName of sfnNameList) {
      sfnObjects.push(
        this.buildStepFunction({
          stateMachineName: sfnName,
          ...props,
        })
      );
    }

    return sfnObjects;
  }

  /** Event bridge rules stuff */
  private buildIcav2AnalysisStateChangeEventPattern(
    props: Icav2AnalysisStateChangeRuleEventPatternProps
  ): EventPattern {
    return {
      detail: {
        'ica-event': {
          // ICA_EXEC_028 is an analysis state change in ICAv2
          eventCode: [props.icav2AnalysisStateChangeEventCode],
          payload: {
            tags: {
              technicalTags: [
                {
                  prefix: props.icav2WesManagerTagKey,
                },
              ],
            },
          },
        },
      },
    };
  }

  private buildIcav2WesPostRequestTarget(props: Icav2WesPostRequestTargetRuleEventPatternProps) {
    return {
      detailType: [props.icav2WesRequestDetailType],
    };
  }

  private buildEventRule(props: EventBridgeRuleProps): Rule {
    return new events.Rule(this, props.ruleName, {
      ruleName: props.ruleName,
      eventPattern: props.eventPattern,
      eventBus: props.eventBus,
    });
  }

  private buildIcav2AnalysisStateChangeRule(props: BuildIcav2AnalysisStateChangeRuleProps): Rule {
    return this.buildEventRule({
      ruleName: props.ruleName,
      eventPattern: this.buildIcav2AnalysisStateChangeEventPattern(props),
      eventBus: props.eventBus,
    });
  }

  private buildIcav2WesPostRequestRule(props: buildIcav2WesPostRequestRuleProps): Rule {
    return this.buildEventRule({
      ruleName: props.ruleName,
      eventPattern: this.buildIcav2WesPostRequestTarget(props),
      eventBus: props.eventBus,
    });
  }

  private buildEventBridgeRules(props: BuildEventBridgeRulesProps): EventBridgeRuleObject[] {
    const eventBridgeObjects: EventBridgeRuleObject[] = [];
    for (const eventBridgeRuleName of eventBridgeRuleNameList) {
      switch (eventBridgeRuleName) {
        case 'icav2AnalysisStateChangeRule': {
          eventBridgeObjects.push({
            ruleName: eventBridgeRuleName,
            ruleObject: this.buildIcav2AnalysisStateChangeRule({
              ruleName: eventBridgeRuleName,
              eventBus: props.internalEventBus,
              icav2AnalysisStateChangeEventCode: props.icav2AnalysisStateChangeEventCode,
              icav2WesManagerTagKey: props.icav2WesManagerTagKey,
            }),
          });
          break;
        }
        case 'icav2WesPostRequestRule': {
          eventBridgeObjects.push({
            ruleName: eventBridgeRuleName,
            ruleObject: this.buildIcav2WesPostRequestRule({
              ruleName: eventBridgeRuleName,
              eventBus: props.externalEventBus,
              icav2WesRequestDetailType: props.icav2WesRequestDetailType,
            }),
          });
          break;
        }
      }
    }
    return eventBridgeObjects;
  }

  /* Event Bridge Target Stuff */
  private buildLambdaEventBridgeTargetWithInputAsDetail(
    props: AddLambdaAsEventBridgeTargetProps
  ): void {
    props.eventBridgeRuleObj.addTarget(
      new eventsTargets.LambdaFunction(props.lambdaFunction.lambdaFunction, {
        event: events.RuleTargetInput.fromEventPath('$.detail'),
      })
    );
  }

  private buildSfnEventBridgeTargetFromIcaEventPipe(props: AddSfnAsEventBridgeTargetProps): void {
    props.eventBridgeRuleObj.addTarget(
      new eventsTargets.SfnStateMachine(props.stateMachineObj, {
        input: events.RuleTargetInput.fromEventPath('$.detail.ica-event.payload'),
      })
    );
  }

  private buildAllEventBridgeTargets(props: EventBridgeTargetsProps): void {
    /* Iterate over each event bridge rule and add the target */
    for (const eventBridgeTargetsName of eventBridgeTargetsNameList) {
      switch (eventBridgeTargetsName) {
        case 'icav2AnalysisStateChangeTargetToHandleStateChangeSfn': {
          this.buildSfnEventBridgeTargetFromIcaEventPipe(<AddSfnAsEventBridgeTargetProps>{
            eventBridgeRuleObj: props.eventBridgeRuleObjects.find(
              (eventBridgeObject) => eventBridgeObject.ruleName === 'icav2AnalysisStateChangeRule'
            )?.ruleObject,
            stateMachineObj: props.stepFunctionObjects.find(
              (eventBridgeObject) =>
                eventBridgeObject.stateMachineName === 'handleIcav2AnalysisStateChange'
            )?.stateMachineObj,
          });
          break;
        }
        case 'icav2WesPostRequestTargetToGenerateWesPostRequestLambda': {
          this.buildLambdaEventBridgeTargetWithInputAsDetail(<AddLambdaAsEventBridgeTargetProps>{
            eventBridgeRuleObj: props.eventBridgeRuleObjects.find(
              (eventBridgeObject) => eventBridgeObject.ruleName === 'icav2WesPostRequestRule'
            )?.ruleObject,
            lambdaFunction: props.lambdaObjects.find(
              (eventBridgeObject) =>
                eventBridgeObject.lambdaName === 'generateWesPostRequestFromEvent'
            ),
          });
          break;
        }
      }
    }
  }

  /** Interfaces */
  private buildApiInterfaceLambda(props: LambdaApiProps) {
    // Create the lambda function
    const lambdaFunction = new PythonUvFunction(this, props.lambdaName, {
      entry: path.join(INTERFACE_DIR),
      runtime: lambda.Runtime.PYTHON_3_12,
      architecture: lambda.Architecture.ARM_64,
      index: 'handler.py',
      handler: 'handler',
      memorySize: 2048,
      includeFastApiLayer: true,
      timeout: Duration.seconds(60),
    });

    // Add SFN arns as environment variables
    // And allow the lambda to invoke the step functions
    for (const sfnObject of props.stepFunctions) {
      sfnObject.stateMachineObj.grantStartExecution(lambdaFunction.currentVersion);
      switch (sfnObject.stateMachineName) {
        case 'launchIcav2Analysis': {
          lambdaFunction.addEnvironment(
            'ICAV2_WES_LAUNCH_STATE_MACHINE_ARN',
            sfnObject.stateMachineObj.stateMachineArn
          );
          break;
        }
        case 'abortIcav2Analysis': {
          lambdaFunction.addEnvironment(
            'ICAV2_WES_ABORT_STATE_MACHINE_ARN',
            sfnObject.stateMachineObj.stateMachineArn
          );
          break;
        }
      }
    }

    // Add the table in as an environment variable
    // And allow the lambda to write + read from the table
    lambdaFunction.addEnvironment('DYNAMODB_ICAV2_WES_ANALYSIS_TABLE_NAME', props.table.tableName);
    lambdaFunction.addEnvironment('DYNAMODB_HOST', `https://dynamodb.${this.region}.amazonaws.com`);
    props.table.grantReadWriteData(lambdaFunction.currentVersion);

    const tableIndexArns: string[] = props.tableIndexNames.map((index_name) => {
      return `arn:aws:dynamodb:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:table/${props.table.tableName}/index/${index_name}-index`;
    });

    // Add index arns to role policy
    lambdaFunction.currentVersion.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['dynamodb:Query'],
        resources: tableIndexArns,
      })
    );

    // Add the event bus in as an environment variable
    // And allow the lambda to put events to the event bus
    lambdaFunction.addEnvironment('EVENT_BUS_NAME', props.eventBus.eventBusName);
    props.eventBus.grantPutEventsTo(lambdaFunction.currentVersion);

    // Few extra env vars
    lambdaFunction.addEnvironment('EVENT_SOURCE', props.eventSource);
    lambdaFunction.addEnvironment(
      'EVENT_DETAIL_TYPE_ANALYSIS_STATE_CHANGE',
      props.icav2WesAnalysisStateChangeEventDetail
    );

    lambdaFunction.addEnvironment('ICAV2_WES_BASE_URL', 'https://icav2-wes.dev.umccr.org');

    // Add in stack suppressions
    NagSuppressions.addResourceSuppressions(lambdaFunction, [
      {
        id: 'AwsSolutions-L1',
        reason: 'Will migrate to PYTHON_3_13 ASAP, soz',
      },
    ]);

    return lambdaFunction;
  }

  private buildApiGateway(props: OrcaBusApiGatewayProps): OrcaBusApiGateway {
    return new OrcaBusApiGateway(this, 'apiGateway', props);
  }

  private buildApiIntegration(props: BuildApiIntegrationProps): HttpLambdaIntegration {
    return new HttpLambdaIntegration('ApiIntegration', props.lambdaFunction);
  }

  // Add the http routes to the API Gateway
  private addHttpRoutes(props: BuildHttpRoutesProps) {
    // Routes for API schemas
    new HttpRoute(this, 'GetSchemaHttpRoute', {
      httpApi: props.apiGateway.httpApi,
      integration: props.apiIntegration,
      authorizer: new HttpNoneAuthorizer(), // No auth needed for schema
      routeKey: HttpRouteKey.with(`/schema/{PROXY+}`, HttpMethod.GET),
    });
    new HttpRoute(this, 'GetHttpRoute', {
      httpApi: props.apiGateway.httpApi,
      integration: props.apiIntegration,
      routeKey: HttpRouteKey.with(`/api/${API_VERSION}/{PROXY+}`, HttpMethod.GET),
    });
    new HttpRoute(this, 'PostHttpRoute', {
      httpApi: props.apiGateway.httpApi,
      integration: props.apiIntegration,
      authorizer: props.apiGateway.authStackHttpLambdaAuthorizer,
      routeKey: HttpRouteKey.with(`/api/${API_VERSION}/{PROXY+}`, HttpMethod.POST),
    });
    new HttpRoute(this, 'PatchHttpRoute', {
      httpApi: props.apiGateway.httpApi,
      integration: props.apiIntegration,
      authorizer: props.apiGateway.authStackHttpLambdaAuthorizer,
      routeKey: HttpRouteKey.with(`/api/${API_VERSION}/{PROXY+}`, HttpMethod.PATCH),
    });
    new HttpRoute(this, 'DeleteHttpRoute', {
      httpApi: props.apiGateway.httpApi,
      integration: props.apiIntegration,
      authorizer: props.apiGateway.authStackHttpLambdaAuthorizer,
      routeKey: HttpRouteKey.with(`/api/${API_VERSION}/{PROXY+}`, HttpMethod.DELETE),
    });
  }

  /* Utils */
  private camelCaseToSnakeCase(camelCase: string): string {
    return camelCase.replace(/([A-Z])/g, '_$1').toLowerCase();
  }
}
