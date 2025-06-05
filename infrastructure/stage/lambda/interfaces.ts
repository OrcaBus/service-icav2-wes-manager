import { PythonFunction } from '@aws-cdk/aws-lambda-python-alpha';

export type LambdaNameList =
  | 'abortAnalysis'
  | 'deleteIcav2Dir'
  | 'generateWesPostRequestFromEvent'
  | 'getIcav2WesObject'
  | 'getLogsDir'
  | 'launchIcav2AnalysisViaWrapica'
  | 'updateStatusOnWesApi';

/* Lambda names array */
/* Bit of double handling, BUT types are not parsed to JS */
export const lambdaNameList: Array<LambdaNameList> = [
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
}

export type LambdaToRequirementsMapType = { [key in LambdaNameList]: LambdaRequirementProps };

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
  },
  updateStatusOnWesApi: {
    needsOrcabusTookitLayer: true,
  },
};

export interface BuildLambdaProps {
  lambdaName: LambdaNameList;
}

export interface LambdaObject extends BuildLambdaProps {
  lambdaFunction: PythonFunction;
}
