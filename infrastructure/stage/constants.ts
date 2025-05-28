/* Directory constants */
import { Duration, RemovalPolicy } from 'aws-cdk-lib';
import path from 'path';

export const APP_ROOT = path.join(__dirname, '../../app');
export const LAMBDA_DIR = path.join(APP_ROOT, 'lambdas');
export const STEP_FUNCTIONS_DIR = path.join(APP_ROOT, 'step-functions-templates');
export const INTERFACE_DIR = path.join(APP_ROOT, 'interface');

export const API_VERSION = 'v1';

/* Event Constants */
export const DEFAULT_EXTERNAL_EVENT_BUS_NAME = 'OrcaBusMain';
export const EVENT_SOURCE = 'orcabus.icav2wesmanager';
export const ICAV2_WES_EVENT_REQUEST_SUBMISSION_STATUS = 'Icav2WesRequest';
export const ICAV2_WES_EVENT_STATE_CHANGE_EVENT_DETAIL_TYPE_EXTERNAL = 'ICAv2WesStateChange';

/* ICAv2 Copy Sync constants */
export const ICAV2_DATA_COPY_SYNC_EVENT_DETAIL_TYPE_EXTERNAL = 'ICAv2DataCopySync';

/* ICA Constants */
export const ICAV2_ANALYSIS_STATE_CHANGE_JOB_EVENT_CODE = 'ICA_EXEC_028';
export const ICAV2_WES_MANAGER_TAG_KEY = 'icav2_wes_orcabus_id';

/* Evvnt pipe constants - stateful stack */
// Event pipe is used to send events from the SQS queue to the event bus
// This is generated in the stateful infrastructure stack and used in the
// stateless infrastructure stack
export const DEFAULT_EVENT_PIPE_NAME = 'Icav2WesAnalysisEventPipe';
// The SQS name should be noted since the ARN is required when
// setting up the notifications of the project
export const DEFAULT_ICA_SQS_NAME = 'Icav2WesAnalysisSqsQueue';
export const DEFAULT_ICA_QUEUE_VIZ_TIMEOUT = Duration.seconds(30);
export const DEFAULT_DLQ_ALARM_THRESHOLD = 1;
export const DEFAULT_ICA_AWS_ACCOUNT_NUMBER = '079623148045';

/* UMCCR / CCGCM constants */

/* Slack constants */
export const SLACK_TOPIC_NAME = 'AwsChatBotTopic';

/* DynamoDB table constants */
export const TABLE_NAME = 'icav2WesManagerApiDynamoDBTable';
export const TABLE_INDEX_NAMES = ['name', 'status'];
export const TABLE_REMOVAL_POLICY = RemovalPolicy.RETAIN_ON_UPDATE_OR_DELETE; // We need to retain the table on update or delete to avoid data loss

/* Event constants */
export const EVENT_BUS_NAME_INTERNAL = 'OrcaBusICAv2WesManagerInternal'; // Events for internal use only, i.e handling ICAV2 Events
export const INTERNAL_EVENT_BUS_DESCRIPTION = 'Event Bus to handle ICAv2 Analysis Events'; // Events for internal use only, i.e handling ICAV2 Events
export const ICAV2_SQS_EVENT_PIPE_NAME = 'Icav2WesManagerEventPipe'; // Event pipe for ICAV2 events to forward to the internal event bus
