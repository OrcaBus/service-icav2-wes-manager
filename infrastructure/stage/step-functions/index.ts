// Imports
import * as sfn from 'aws-cdk-lib/aws-stepfunctions';
import { Construct } from 'constructs';
import * as path from 'path';

// Local interfaces
import {
  BuildSfnsProps,
  sfnNameList,
  SfnObjectProps,
  SfnProps,
  sfnToRequirementsMap,
  stepFunctionToLambdaMap,
} from './interfaces';
import { camelCaseToSnakeCase } from '../utils';
import { STEP_FUNCTIONS_DIR } from '../constants';
import { NagSuppressions } from 'cdk-nag';

/** Step Function stuff */
function createStateMachineDefinitionSubstitutions(props: SfnProps): {
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
    const sfnSubtitutionKey = `__${camelCaseToSnakeCase(lambdaObject.lambdaName)}_lambda_function_arn__`;
    definitionSubstitutions[sfnSubtitutionKey] =
      lambdaObject.lambdaFunction.currentVersion.functionArn;
  }

  /* Sfn Requirements */
  if (sfnRequirements.needsExternalEventBusPutPermissions) {
    definitionSubstitutions['__external_event_bus_name__'] = props.eventBus.eventBusName;
    definitionSubstitutions['__icav2_data_copy_sync_detail_type__'] = props.icav2DataCopySyncDetail;
    definitionSubstitutions['__stack_source__'] = props.eventSource;
  }

  if (sfnRequirements.needsPayloadDbPermissions) {
    definitionSubstitutions['__payloads_table_name__'] = props.payloadsTable.tableName;
  }

  return definitionSubstitutions;
}

function wireUpStateMachinePermissions(props: SfnObjectProps): void {
  /* Wire up lambda permissions */
  const sfnRequirements = sfnToRequirementsMap[props.stateMachineName];

  const lambdaFunctionNamesInSfn = stepFunctionToLambdaMap[props.stateMachineName];
  const lambdaFunctions = props.lambdaFunctions.filter((lambdaObject) =>
    lambdaFunctionNamesInSfn.includes(lambdaObject.lambdaName)
  );

  if (sfnRequirements.needsExternalEventBusPutPermissions) {
    props.eventBus.grantPutEventsTo(props.stateMachineObj);
  }

  if (sfnRequirements.needsPayloadDbPermissions) {
    props.payloadsTable.grantReadWriteData(props.stateMachineObj);
  }

  /* Allow the state machine to invoke the lambda function */
  for (const lambdaObject of lambdaFunctions) {
    lambdaObject.lambdaFunction.currentVersion.grantInvoke(props.stateMachineObj);
  }
}

function buildStepFunction(scope: Construct, props: SfnProps): SfnObjectProps {
  const sfnNameToSnakeCase = camelCaseToSnakeCase(props.stateMachineName);

  /* Create the state machine definition substitutions */
  const stateMachine = new sfn.StateMachine(scope, props.stateMachineName, {
    stateMachineName: `icav2-wes-${props.stateMachineName}`,
    definitionBody: sfn.DefinitionBody.fromFile(
      path.join(STEP_FUNCTIONS_DIR, sfnNameToSnakeCase + `_sfn_template.asl.json`)
    ),
    definitionSubstitutions: createStateMachineDefinitionSubstitutions(props),
  });

  /* Grant the state machine permissions */
  wireUpStateMachinePermissions({
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

export function buildAllStepFunctions(scope: Construct, props: BuildSfnsProps): SfnObjectProps[] {
  // Initialize the step function objects
  const sfnObjects = [] as SfnObjectProps[];

  // Iterate over lambdaLayerToMapping and create the lambda functions
  for (const sfnName of sfnNameList) {
    sfnObjects.push(
      buildStepFunction(scope, {
        stateMachineName: sfnName,
        ...props,
      })
    );
  }

  return sfnObjects;
}
