/* Directory constants */
import { Duration, RemovalPolicy } from 'aws-cdk-lib';
import path from 'path';
import {
  ACCOUNT_ID_ALIAS,
  REGION,
  StageName,
} from '@orcabus/platform-cdk-constructs/shared-config/accounts';
import { EVENT_SCHEMA_REGISTRY_NAME } from '@orcabus/platform-cdk-constructs/shared-config/event-bridge';

/* Application dirs */
export const APP_ROOT = path.join(__dirname, '../../app');
export const LAMBDA_DIR = path.join(APP_ROOT, 'lambdas');
export const STEP_FUNCTIONS_DIR = path.join(APP_ROOT, 'step-functions-templates');
export const INTERFACE_DIR = path.join(APP_ROOT, 'interface');
export const EVENT_SCHEMAS_DIR = path.join(APP_ROOT, 'event-schemas');

/* API constants */
export const API_VERSION = 'v1';
export const ICAV2_WES_SUBDOMAIN_NAME = 'icav2-wes';
export const STACK_PREFIX = 'icav2-wes';

/* Event Constants */
export const DEFAULT_EXTERNAL_EVENT_BUS_NAME = 'OrcaBusMain';
export const EVENT_SOURCE = 'orcabus.icav2wesmanager';
export const ICAV2_WES_EVENT_REQUEST_SUBMISSION_STATUS = 'Icav2WesRequest';
export const ICAV2_WES_EVENT_STATE_CHANGE_EVENT_DETAIL_TYPE_EXTERNAL =
  'Icav2WesAnalysisStateChange';

/* Bucket constants */
export const S3_ARTEFACTS_BUCKET_NAME: Record<StageName, string> = {
  BETA: `icav2-wes-artifacts-${ACCOUNT_ID_ALIAS.BETA}-${REGION}`,
  GAMMA: `icav2-wes-artifacts-${ACCOUNT_ID_ALIAS.GAMMA}-${REGION}`,
  PROD: `icav2-wes-artifacts-${ACCOUNT_ID_ALIAS.PROD}-${REGION}`,
};
export const PAYLOADS_KEY_PREFIX = 'analysis-payloads/';
export const ERROR_LOGS_KEY_PREFIX = 'error-logs/';

/* ICA Constants */
export const ICAV2_ANALYSIS_STATE_CHANGE_JOB_EVENT_CODE = 'ICA_EXEC_028';
export const ICAV2_WES_MANAGER_TAG_KEY = 'icav2_wes_orcabus_id';

/* SQS */
// SHARED QUEUE PARAMS
export const DEFAULT_QUEUE_TIMEOUT = Duration.seconds(300);
export const DEFAULT_DLQ_ALARM_THRESHOLD = 1;
export const SLACK_TOPIC_NAME = 'AwsChatBotTopic';

// Launch ICA Analysis SQS
export const DEFAULT_LAUNCH_ICA_ANALYSIS_SQS_QUEUE_NAME = 'Icav2WesLaunchIcaAnalysisSqsQueue';
export const DEFAULT_LAUNCH_ICA_ANALYSIS_EVENT_PIPE_NAME = 'Icav2WesLaunchIcaAnalysisEventPipe';

// External SQS
// The SQS queue pushes directly to the handleAnalysisStateChange step function
// The SQS name should be noted since the ARN is required when
// setting up the notifications of the project
export const DEFAULT_EXTERNAL_ICA_EVENT_SQS_NAME = 'Icav2WesAnalysisSqsQueue';
export const DEFAULT_EXTERNAL_ICA_EVENT_PIPE_NAME = 'Icav2WesSqsEventPipe';
export const DEFAULT_ICA_AWS_ACCOUNT_NUMBER = '079623148045';

/* SSM Constants */
export const SSM_PARAMETER_PATH_PREFIX = path.join(`/orcabus/icav2-wes/`);

/* UMCCR / CCGCM constants */

/* DynamoDB table constants */
export const TABLE_NAME = 'icav2WesManagerApiDynamoDBTable';
export const TABLE_INDEX_NAMES = ['name', 'status'];
export const TABLE_REMOVAL_POLICY = RemovalPolicy.RETAIN_ON_UPDATE_OR_DELETE; // We need to retain the table on update or delete to avoid data loss

/* Extra tables */
export const PAYLOADS_TABLE_NAME = 'icav2WesManagerPayloadsTable';

/* Event constants */
export const EVENT_BUS_NAME_INTERNAL = 'OrcaBusICAv2WesManagerInternal'; // Events for internal use only, i.e handling ICAV2 Events
export const INTERNAL_EVENT_BUS_DESCRIPTION = 'Event Bus to handle ICAv2 Analysis Events'; // Events for internal use only, i.e handling ICAV2 Events

/* Schema constants */
export const SCHEMA_REGISTRY_NAME = EVENT_SCHEMA_REGISTRY_NAME;
export const SSM_SCHEMA_ROOT = path.join(SSM_PARAMETER_PATH_PREFIX, 'schemas');
