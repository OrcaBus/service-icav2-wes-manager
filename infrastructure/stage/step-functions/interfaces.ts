import { IEventBus } from 'aws-cdk-lib/aws-events';
import { StateMachine } from 'aws-cdk-lib/aws-stepfunctions';
import { LambdaName, LambdaObject } from '../lambda/interfaces';
import { ITableV2 } from 'aws-cdk-lib/aws-dynamodb';

export type SfnName =
  | 'abortIcav2Analysis'
  | 'handleIcav2AnalysisStateChange'
  | 'launchIcav2Analysis';

export const sfnNameList: Array<SfnName> = [
  'abortIcav2Analysis',
  'handleIcav2AnalysisStateChange',
  'launchIcav2Analysis',
];

export interface BuildSfnsProps {
  /* Naming formation */
  lambdaFunctions: Array<LambdaObject>;

  /* The event bus to use */
  eventBus: IEventBus;
  eventSource: string;
  payloadsTable: ITableV2;
  callbackTable: ITableV2;
}

export interface SfnProps extends BuildSfnsProps {
  /* Naming formation */
  stateMachineName: SfnName;
}

export interface SfnObjectProps extends SfnProps {
  /* The state machine object */
  stateMachineObj: StateMachine;
}

export const stepFunctionToLambdaMap: { [key in SfnName]: Array<LambdaName> } = {
  abortIcav2Analysis: ['abortAnalysis'],
  handleIcav2AnalysisStateChange: [
    'addPortalRunIdAttributes',
    'updateStatusOnWesApi',
    'getIcav2WesObject',
    'getPipelineType',
    'copyNextflowFilesFromLogsUri',
    'filemanagerSync',
  ],
  launchIcav2Analysis: [
    'launchIcav2AnalysisViaWrapica',
    'updateStatusOnWesApi',
    'unlockCallbackId',
  ],
};

export interface SfnRequirementsProps {
  /*
  Event Bus Stuff - required only for the handleIcav2AnalysisStateChange state machine
  This state machine needs to put permissions on the external event bus
  in order to copy the log files into the proper location
  */
  needsExternalEventBusPutPermissions?: boolean;
  isExpressSfn?: boolean;
  needsPayloadDbPermissions?: boolean;
  needsCallbackTablePermissions?: boolean;
}

export type SfnToRequirementsMapType = { [key in SfnName]: SfnRequirementsProps };

export const sfnToRequirementsMap: SfnToRequirementsMapType = {
  abortIcav2Analysis: {
    needsExternalEventBusPutPermissions: false,
  },
  handleIcav2AnalysisStateChange: {
    needsExternalEventBusPutPermissions: true,
    isExpressSfn: true,
  },
  launchIcav2Analysis: {
    needsExternalEventBusPutPermissions: false,
    needsPayloadDbPermissions: true,
  },
};
