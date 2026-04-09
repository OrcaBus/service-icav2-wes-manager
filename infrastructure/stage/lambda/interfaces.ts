import { PythonFunction } from '@aws-cdk/aws-lambda-python-alpha';
import { IBucket } from 'aws-cdk-lib/aws-s3';
import { IQueue } from 'aws-cdk-lib/aws-sqs';
import { ITableV2 } from 'aws-cdk-lib/aws-dynamodb';
import { SfnName } from '../step-functions/interfaces';

export type LambdaName =
  // Shared functions
  | 'getIcav2WesObject'
  // Pre analysis
  | 'generateWesPostRequestFromEvent'
  // Run analysis
  | 'launchIcav2AnalysisViaWrapica'
  | 'unlockCallbackId'
  // Mid analysis
  | 'updateStatusOnWesApi'
  | 'abortAnalysis'
  // ICA event handling
  | 'handleIcaEvent'
  // Post analysis
  // Handle nextflow files
  | 'getPipelineType'
  | 'copyNextflowFilesFromLogsUri'
  // Handle Filemanager
  | 'addPortalRunIdAttributes'
  | 'filemanagerSync'
  // Handle task summaries
  | 'listTasksInAnalysis' // Not yet implemented
  | 'getAndRegisterAnalysisTasks' // Not yet implemented
  | 'addTaskAnomaliesToWorkflowManager' // Not yet implemented
  // Handle corrupted files
  | 'getOutputFileIngestIds' // Not yet implemented
  | 'getMatchingIngestIds' // Not yet implemented
  | 'isBamFile' // Not yet implemented
  | 'getFileUriFromIngestId' // Not yet implemented
  | 'isFileCorrupted' // Not yet implemented
  // Unlock callback id
  // Get Usage
  | 'collectNonPriceUsageMetrics' // Not yet implemented
  | 'getIcav2WesCostUsagePrice' // Not yet implemented
  | 'addUsageCosts' // Not yet implemented
  | 'addCostSummariesCommentToWorkflowManager'; // Not yet implemented

/* Lambda names array */
/* Bit of double handling, BUT types are not parsed to JS */
export const lambdaNameList: Array<LambdaName> = [
  // Shared functions
  'getIcav2WesObject',
  // Pre analysis
  'generateWesPostRequestFromEvent',
  // Run analysis
  'launchIcav2AnalysisViaWrapica',
  'unlockCallbackId',
  // Mid analysis
  'updateStatusOnWesApi',
  'abortAnalysis',
  // ICA event handling
  'handleIcaEvent',
  // Post analysis
  // Handle nextflow files
  'getPipelineType',
  'copyNextflowFilesFromLogsUri',
  // Handle Filemanager
  'addPortalRunIdAttributes',
  'filemanagerSync',
  // Handle task summaries
  // 'listTasksInAnalysis', // Not yet implemented
  // 'getAndRegisterAnalysisTasks', // Not yet implemented
  // 'addTaskAnomaliesToWorkflowManager', // Not yet implemented
  // Handle corrupted files
  // 'getOutputFileIngestIds',  // Not yet implemented
  // 'getMatchingIngestIds',  // Not yet implemented
  // 'isBamFile',  // Not yet implemented
  // 'getFileUriFromIngestId',  // Not yet implemented
  // 'isFileCorrupted',  // Not yet implemented
  // Unlock callback id
  // Get Usage
  // 'collectNonPriceUsageMetrics',  // Not yet implemented
  // 'getIcav2WesCostUsagePrice',  // Not yet implemented
  // 'addUsageCosts',  // Not yet implemented
  // 'addCostSummariesCommentToWorkflowManager',  // Not yet implemented
];

/* We also throw in our custom application interfaces here too */
export interface LambdaRequirementProps {
  needsIcav2ToolkitLayer?: boolean;
  needsOrcabusTookitLayer?: boolean;
  needsTestDataBucketPermissions?: boolean;
  needsReferenceDataBucketPermissions?: boolean;
  needsArtefactBucketPermissions?: boolean;
  needsSqsEventSource?: boolean;
  needsCallbackPermissions?: boolean;
  needsDurableExecutionPermissions?: boolean;
  needsCallbackDbPermissions?: boolean;
}

export type LambdaToRequirementsMapType = { [key in LambdaName]: LambdaRequirementProps };

export const lambdaToRequirementsMap: LambdaToRequirementsMapType = {
  // Shared functions
  getIcav2WesObject: {
    needsOrcabusTookitLayer: true,
    needsIcav2ToolkitLayer: true,
  },
  // Pre analysis
  generateWesPostRequestFromEvent: {
    needsOrcabusTookitLayer: true,
    needsSqsEventSource: true,
    needsDurableExecutionPermissions: true,
    needsCallbackDbPermissions: true,
  },
  // Run analysis
  launchIcav2AnalysisViaWrapica: {
    needsIcav2ToolkitLayer: true,
    needsOrcabusTookitLayer: true,
    needsTestDataBucketPermissions: true,
    needsReferenceDataBucketPermissions: true,
    needsArtefactBucketPermissions: true,
  },
  unlockCallbackId: {
    needsCallbackPermissions: true,
  },
  // Mid analysis
  updateStatusOnWesApi: {
    needsOrcabusTookitLayer: true,
    needsArtefactBucketPermissions: true,
  },
  abortAnalysis: {
    needsIcav2ToolkitLayer: true,
  },
  // ICA Event
  handleIcaEvent: {
    needsOrcabusTookitLayer: true,
    needsSqsEventSource: true,
    needsDurableExecutionPermissions: true,
    needsCallbackDbPermissions: true,
  },
  // Post analysis
  // Handle nextflow files
  getPipelineType: {
    needsOrcabusTookitLayer: true,
    needsIcav2ToolkitLayer: true,
  },
  copyNextflowFilesFromLogsUri: {
    needsIcav2ToolkitLayer: true,
  },
  // Handle Filemanager
  addPortalRunIdAttributes: {
    needsOrcabusTookitLayer: true,
  },
  filemanagerSync: {
    needsOrcabusTookitLayer: true,
    needsIcav2ToolkitLayer: true,
  },
  // Handle task summaries
  listTasksInAnalysis: {
    // Not yet implemented
  },
  getAndRegisterAnalysisTasks: {
    // Not yet implemented
  },
  addTaskAnomaliesToWorkflowManager: {
    // Not yet implemented
  },
  // Handle corrupted files
  getOutputFileIngestIds: {
    // Not yet implemented
  },
  getMatchingIngestIds: {
    // Not yet implemented
  },
  isBamFile: {
    // Not yet implemented
  },
  getFileUriFromIngestId: {
    // Not yet implemented
  },
  isFileCorrupted: {
    // Not yet implemented
  },
  // Unlock callback id
  // Get Usage
  collectNonPriceUsageMetrics: {
    // Not yet implemented
  },
  getIcav2WesCostUsagePrice: {
    // Not yet implemented
  },
  addUsageCosts: {
    // Not yet implemented
  },
  addCostSummariesCommentToWorkflowManager: {
    // Not yet implemented
  },
};

export interface BuildLambdaProps {
  lambdaName: LambdaName;
  testDataBucket: IBucket;
  referenceDataBucket: IBucket;
  artefactsBucket: IBucket;
  payloadsKeyPrefix: string;
  errorLogsKeyPrefix: string;
  generateWesPostRequestEventQueue: IQueue;
  externalIcaEventQueue: IQueue;
  callbackTable: ITableV2;
  handleIcaStateChangeSfnName: SfnName;
}

export type BuildAllLambdasProps = Omit<BuildLambdaProps, 'lambdaName'>;

export interface LambdaObject {
  lambdaName: LambdaName;
  lambdaFunction: PythonFunction;
}
