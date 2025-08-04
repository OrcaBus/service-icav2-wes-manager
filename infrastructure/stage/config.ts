import { StatefulApplicationStackConfig, StatelessApplicationStackConfig } from './interfaces';
import { getDefaultApiGatewayConfiguration } from '@orcabus/platform-cdk-constructs/api-gateway';

import {
  DEFAULT_EVENT_PIPE_NAME,
  DEFAULT_EXTERNAL_EVENT_BUS_NAME,
  EVENT_BUS_NAME_INTERNAL,
  EVENT_SOURCE,
  ICAV2_ANALYSIS_STATE_CHANGE_JOB_EVENT_CODE,
  ICAV2_DATA_COPY_SYNC_EVENT_DETAIL_TYPE_EXTERNAL,
  ICAV2_WES_EVENT_REQUEST_SUBMISSION_STATUS,
  ICAV2_WES_EVENT_STATE_CHANGE_EVENT_DETAIL_TYPE_EXTERNAL,
  ICAV2_WES_MANAGER_TAG_KEY,
  INTERNAL_EVENT_BUS_DESCRIPTION,
  SLACK_TOPIC_NAME,
  TABLE_INDEX_NAMES,
  TABLE_NAME,
} from './constants';
import { ICAV2_ACCESS_TOKEN_SECRET_ID } from '@orcabus/platform-cdk-constructs/shared-config/icav2';
import { HOSTED_ZONE_DOMAIN_PARAMETER_NAME } from '@orcabus/platform-cdk-constructs/api-gateway';
import { StageName } from '@orcabus/platform-cdk-constructs/shared-config/accounts';

export const getStatefulStackProps = (): StatefulApplicationStackConfig => {
  return {
    // Table stuff
    tableName: TABLE_NAME,
    indexNames: TABLE_INDEX_NAMES,

    // Internal Event stuff
    internalEventBusName: EVENT_BUS_NAME_INTERNAL,
    internalEventBusDescription: INTERNAL_EVENT_BUS_DESCRIPTION,
    icav2EventPipeName: DEFAULT_EVENT_PIPE_NAME,
    slackTopicName: SLACK_TOPIC_NAME,
  };
};

export const getStatelessStackProps = (stage: StageName): StatelessApplicationStackConfig => {
  return {
    // Stage stuff
    stageName: stage,
    // Event stuff
    eventSource: EVENT_SOURCE,
    externalEventBusName: DEFAULT_EXTERNAL_EVENT_BUS_NAME,

    // External event handling stuff
    icav2WesAnalysisStateChangeDetailType: ICAV2_WES_EVENT_STATE_CHANGE_EVENT_DETAIL_TYPE_EXTERNAL,
    icav2WesManagerTagKey: ICAV2_WES_MANAGER_TAG_KEY,
    icav2WesRequestDetailType: ICAV2_WES_EVENT_REQUEST_SUBMISSION_STATUS,
    icav2DataCopySyncDetailType: ICAV2_DATA_COPY_SYNC_EVENT_DETAIL_TYPE_EXTERNAL,

    // Internal event handling stuff
    internalEventBusName: EVENT_BUS_NAME_INTERNAL,
    icav2EventPipeName: DEFAULT_EVENT_PIPE_NAME,
    icav2AnalysisStateChangeEventCode: ICAV2_ANALYSIS_STATE_CHANGE_JOB_EVENT_CODE,

    // Table stuff
    tableName: TABLE_NAME,
    indexNames: TABLE_INDEX_NAMES,

    // Hostname ssm parameter
    hostedZoneSsmParameterName: HOSTED_ZONE_DOMAIN_PARAMETER_NAME,

    // ICAV2 access token secret
    icav2AccessTokenSecretId: ICAV2_ACCESS_TOKEN_SECRET_ID[stage],

    // API Gateway stuff
    apiGatewayCognitoProps: {
      ...getDefaultApiGatewayConfiguration(stage),
      apiName: 'ICAv2WesManager',
      customDomainNamePrefix: 'icav2-wes',
    },
  };
};
