import { PythonFunction } from '@aws-cdk/aws-lambda-python-alpha';
import { IBucket } from 'aws-cdk-lib/aws-s3';

export type LambdaName =
  | 'abortAnalysis'
  | 'deleteIcav2Dir'
  | 'generateWesPostRequestFromEvent'
  | 'getIcav2WesObject'
  | 'getLogsDir'
  | 'launchIcav2AnalysisViaWrapica'
  | 'updateStatusOnWesApi';

/* Lambda names array */
/* Bit of double handling, BUT types are not parsed to JS */
export const lambdaNameList: Array<LambdaName> = [
  'abortAnalysis',
  'deleteIcav2Dir',
  'generateWesPostRequestFromEvent',
  'getIcav2WesObject',
  'getLogsDir',
  'launchIcav2AnalysisViaWrapica',
  'updateStatusOnWesApi',
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
  abortAnalysis: {
    needsIcav2ToolkitLayer: true,
  },
  deleteIcav2Dir: {
    needsIcav2ToolkitLayer: true,
  },
  generateWesPostRequestFromEvent: {
    needsOrcabusTookitLayer: true,
  },
  getIcav2WesObject: {
    needsOrcabusTookitLayer: true,
  },
  getLogsDir: {
    needsIcav2ToolkitLayer: true,
  },
  launchIcav2AnalysisViaWrapica: {
    needsIcav2ToolkitLayer: true,
    needsOrcabusTookitLayer: true,
    needsTestDataBucketPermissions: true,
    needsReferenceDataBucketPermissions: true,
    needsPayloadsBucketPermissions: true,
  },
  updateStatusOnWesApi: {
    needsOrcabusTookitLayer: true,
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
