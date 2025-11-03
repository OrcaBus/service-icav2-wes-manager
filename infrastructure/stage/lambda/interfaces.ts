import { PythonFunction } from '@aws-cdk/aws-lambda-python-alpha';
import { IBucket } from 'aws-cdk-lib/aws-s3';

export type LambdaName =
  // Pre analysis
  | 'generateWesPostRequestFromEvent'
  // Run analysis
  | 'launchIcav2AnalysisViaWrapica'
  // Mid analysis
  | 'getIcav2WesObject'
  | 'updateStatusOnWesApi'
  | 'abortAnalysis'
  // Post analysis
  | 'addPortalRunIdAttributes'
  | 'getPipelineType'
  | 'copyNextflowFilesFromLogsUri'
  | 'filemanagerSync';

/* Lambda names array */
/* Bit of double handling, BUT types are not parsed to JS */
export const lambdaNameList: Array<LambdaName> = [
  // Pre analysis
  'generateWesPostRequestFromEvent',
  // Run analysis
  'launchIcav2AnalysisViaWrapica',
  // Mid analysis
  'getIcav2WesObject',
  'updateStatusOnWesApi',
  'abortAnalysis',
  // Post analysis
  'addPortalRunIdAttributes',
  'getPipelineType',
  'copyNextflowFilesFromLogsUri',
  'filemanagerSync',
];

/* We also throw in our custom application interfaces here too */
export interface LambdaRequirementProps {
  needsIcav2ToolkitLayer?: boolean;
  needsOrcabusTookitLayer?: boolean;
  needsTestDataBucketPermissions?: boolean;
  needsReferenceDataBucketPermissions?: boolean;
  needsPayloadsBucketPermissions?: boolean;
}

export type LambdaToRequirementsMapType = { [key in LambdaName]: LambdaRequirementProps };

export const lambdaToRequirementsMap: LambdaToRequirementsMapType = {
  // Pre analysis
  generateWesPostRequestFromEvent: {
    needsOrcabusTookitLayer: true,
  },
  // Run analysis
  launchIcav2AnalysisViaWrapica: {
    needsIcav2ToolkitLayer: true,
    needsOrcabusTookitLayer: true,
    needsTestDataBucketPermissions: true,
    needsReferenceDataBucketPermissions: true,
    needsPayloadsBucketPermissions: true,
  },
  // Mid analysis
  getIcav2WesObject: {
    needsOrcabusTookitLayer: true,
    needsIcav2ToolkitLayer: true,
  },
  updateStatusOnWesApi: {
    needsOrcabusTookitLayer: true,
  },
  abortAnalysis: {
    needsIcav2ToolkitLayer: true,
  },
  // Post analysis
  addPortalRunIdAttributes: {
    needsOrcabusTookitLayer: true,
  },
  getPipelineType: {
    needsOrcabusTookitLayer: true,
    needsIcav2ToolkitLayer: true,
  },
  copyNextflowFilesFromLogsUri: {
    needsIcav2ToolkitLayer: true,
  },
  filemanagerSync: {
    needsOrcabusTookitLayer: true,
    needsIcav2ToolkitLayer: true,
  },
};

export interface BuildLambdaProps {
  lambdaName: LambdaName;
  testDataBucket: IBucket;
  referenceDataBucket: IBucket;
  payloadsBucket: IBucket;
  payloadsKeyPrefix: string;
}

export type BuildAllLambdasProps = Omit<BuildLambdaProps, 'lambdaName'>;

export interface LambdaObject {
  lambdaName: LambdaName;
  lambdaFunction: PythonFunction;
}
