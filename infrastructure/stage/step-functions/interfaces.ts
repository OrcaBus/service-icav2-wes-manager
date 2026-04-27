import { IEventBus } from 'aws-cdk-lib/aws-events';
import { StateMachine } from 'aws-cdk-lib/aws-stepfunctions';
import { LambdaName, LambdaObject } from '../lambda/interfaces';
import { ITableV2 } from 'aws-cdk-lib/aws-dynamodb';
import { EcsTaskName, EcsTaskObject } from '../ecs/interfaces';
import { IQueue } from 'aws-cdk-lib/aws-sqs';

export type SfnName =
  | 'abortIcav2Analysis'
  | 'handleIcav2AnalysisStateChange'
  | 'launchIcav2Analysis'
  // Nested handleIcav2AnalysisStateChange functions
  | 'getTaskSummaries' // Not yet implemented
  | 'getUsage' // Not yet implemented
  | 'handleCorruptedFiles'
  | 'handleFilemanager'
  | 'handleNextflowFiles'
  | 'unlockCallbackId';

export const sfnNameList: Array<SfnName> = [
  'abortIcav2Analysis',
  'handleIcav2AnalysisStateChange',
  'launchIcav2Analysis',
  // Nested handleIcav2AnalysisStateChange functions
  // 'getTaskSummaries',  // Not yet implemented
  // 'getUsage',  // Not yet implemented
  'handleCorruptedFiles',
  'handleFilemanager',
  'handleNextflowFiles',
  'unlockCallbackId',
];

export interface BuildSfnsProps {
  /* Naming formation */
  lambdaFunctions: LambdaObject[];
  ecsTaskObjects: EcsTaskObject[];
  /* The event bus to use */
  eventBus: IEventBus;
  eventSource: string;
  payloadsTable: ITableV2;
  callbackTable: ITableV2;
  /* SQS Stuff */
  icaExternalSqsQueue: IQueue;
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
    'updateStatusOnWesApi',
    'getIcav2WesObject',
    'copyNextflowFilesFromLogsUri',
    'filemanagerSync',
    'getMatchingIngestIds',
    'getOutputFileIngestIds',
    'getFileUriFromIngestId',
    'isBamFile',
    'isFileCorrupted',
    'unlockCallbackId',
  ],
  launchIcav2Analysis: [
    'launchIcav2AnalysisViaWrapica',
    'updateStatusOnWesApi',
    'unlockCallbackId',
  ],
  // Nested handleIcav2AnalysisStateChange functions
  getTaskSummaries: [
    'listTasksInAnalysis',
    'getAndRegisterAnalysisTasks',
    'addTaskAnomaliesToWorkflowManager',
  ],
  getUsage: [
    'collectNonPriceUsageMetrics',
    'getIcav2WesCostUsagePrice',
    'addUsageCosts',
    'addCostSummariesCommentToWorkflowManager',
  ],
  handleCorruptedFiles: [
    'getIcav2WesObject',
    'getOutputFileIngestIds',
    'getMatchingIngestIds',
    'isBamFile',
    'getFileUriFromIngestId',
    'isFileCorrupted',
  ],
  handleFilemanager: ['getIcav2WesObject', 'addPortalRunIdAttributes', 'filemanagerSync'],
  handleNextflowFiles: ['getIcav2WesObject', 'getPipelineType', 'copyNextflowFilesFromLogsUri'],
  unlockCallbackId: ['unlockCallbackId'],
};

export const stepFunctionEcsMap: { [key in SfnName]: Array<EcsTaskName> } = {
  abortIcav2Analysis: [],
  handleIcav2AnalysisStateChange: [],
  launchIcav2Analysis: [],
  getTaskSummaries: [],
  getUsage: [],
  handleCorruptedFiles: ['validateBamFile'],
  handleFilemanager: [],
  handleNextflowFiles: [],
  unlockCallbackId: [],
};

export interface SfnRequirementsProps {
  /*
  Event Bus Stuff - required only for the handleIcav2AnalysisStateChange state machine
  This state machine needs to put permissions on the external event bus
  in order to copy the log files into the proper location
  */
  needsExternalEventBusPutPermissions?: boolean;
  needsPayloadDbPermissions?: boolean;
  needsCallbackTablePermissions?: boolean;
  needsDistributedMapSupport?: boolean;
  needsEcsPermissions?: boolean;
  needsSetVisibilityTimeoutPermissions?: boolean;
  needsNestedSfnStartExecutionPermissions?: boolean;
}

export type SfnToRequirementsMapType = { [key in SfnName]: SfnRequirementsProps };

export const sfnToRequirementsMap: SfnToRequirementsMapType = {
  abortIcav2Analysis: {
    needsExternalEventBusPutPermissions: false,
  },
  handleIcav2AnalysisStateChange: {
    needsExternalEventBusPutPermissions: true,
    needsSetVisibilityTimeoutPermissions: true,
    needsNestedSfnStartExecutionPermissions: true,
  },
  launchIcav2Analysis: {
    needsExternalEventBusPutPermissions: false,
    needsPayloadDbPermissions: true,
    needsCallbackTablePermissions: true,
  },
  getTaskSummaries: {
    needsDistributedMapSupport: true,
  },
  getUsage: {}, // Just some lambdas
  handleCorruptedFiles: {
    needsDistributedMapSupport: true,
    needsEcsPermissions: true,
  },
  handleFilemanager: {}, // Just some lambdas
  handleNextflowFiles: {}, // Just some lambdas
  unlockCallbackId: {
    needsCallbackTablePermissions: true,
  },
};
