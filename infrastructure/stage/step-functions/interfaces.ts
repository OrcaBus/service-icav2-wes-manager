import { IEventBus } from 'aws-cdk-lib/aws-events';
import { StateMachine } from 'aws-cdk-lib/aws-stepfunctions';
import { LambdaName, LambdaObject } from '../lambda/interfaces';
import { ITableV2 } from 'aws-cdk-lib/aws-dynamodb';

export type SfnNameList =
  | 'abortIcav2Analysis'
  | 'handleIcav2AnalysisStateChange'
  | 'launchIcav2Analysis';

export const sfnNameList: Array<SfnNameList> = [
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
  icav2DataCopySyncDetail: string;
  payloadsTable: ITableV2;
}

export interface SfnProps extends BuildSfnsProps {
  /* Naming formation */
  stateMachineName: SfnNameList;
}

export interface SfnObjectProps extends SfnProps {
  /* The state machine object */
  stateMachineObj: StateMachine;
}

export const stepFunctionToLambdaMap: { [key in SfnNameList]: Array<LambdaName> } = {
  abortIcav2Analysis: ['abortAnalysis'],
  handleIcav2AnalysisStateChange: [
    'deleteIcav2Dir',
    'updateStatusOnWesApi',
    'getLogsDir',
    'getIcav2WesObject',
  ],
  launchIcav2Analysis: ['launchIcav2AnalysisViaWrapica', 'updateStatusOnWesApi'],
};

export interface SfnRequirementsProps {
  /*
  Event Bus Stuff - required only for the handleIcav2AnalysisStateChange state machine
  This state machine needs to put permissions on the external event bus
  in order to copy the log files into the proper location
  */
  needsExternalEventBusPutPermissions?: boolean;
  needsPayloadDbPermissions?: boolean;
}

export type SfnToRequirementsMapType = { [key in SfnNameList]: SfnRequirementsProps };

export const sfnToRequirementsMap: SfnToRequirementsMapType = {
  abortIcav2Analysis: {
    needsExternalEventBusPutPermissions: false,
  },
  handleIcav2AnalysisStateChange: {
    needsExternalEventBusPutPermissions: true,
  },
  launchIcav2Analysis: {
    needsExternalEventBusPutPermissions: false,
    needsPayloadDbPermissions: true,
  },
};
