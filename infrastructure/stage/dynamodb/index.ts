import { GlobalSecondaryIndexPropsV2 } from 'aws-cdk-lib/aws-dynamodb/lib/table-v2';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import { AttributeType } from 'aws-cdk-lib/aws-dynamodb';
import { TABLE_REMOVAL_POLICY } from '../constants';
import { BuildICAv2WesDbProps, CallbackTableProps, PayloadsTableProps } from './interfaces';
import { Construct } from 'constructs';
import { RemovalPolicy } from 'aws-cdk-lib';

export function buildICAv2WesDb(scope: Construct, props: BuildICAv2WesDbProps) {
  /*
        First generate the global secondary index for the 'name' field
        Hopefully this construct will be useful for other projects as well
        */
  const globalSecondaryIndexes: GlobalSecondaryIndexPropsV2[] = [];
  for (const indexName of props.indexNames) {
    globalSecondaryIndexes.push({
      indexName: `${indexName}-index`,
      partitionKey: {
        name: indexName,
        type: AttributeType.STRING,
      },
      sortKey: {
        name: 'id',
        type: AttributeType.STRING,
      },
    });
  }

  new dynamodb.TableV2(scope, props.tableName, {
    partitionKey: {
      name: 'id',
      type: AttributeType.STRING,
    },
    tableName: props.tableName,
    removalPolicy: TABLE_REMOVAL_POLICY,
    pointInTimeRecoverySpecification: {
      pointInTimeRecoveryEnabled: true,
    },
    timeToLiveAttribute: 'ttl',
    globalSecondaryIndexes: globalSecondaryIndexes,
  });
}

export function buildPayloadsTable(scope: Construct, props: PayloadsTableProps) {
  new dynamodb.TableV2(scope, props.tableName, {
    partitionKey: {
      name: 'id',
      type: AttributeType.STRING,
    },
    tableName: props.tableName,
    removalPolicy: TABLE_REMOVAL_POLICY,
    pointInTimeRecoverySpecification: {
      pointInTimeRecoveryEnabled: true,
    },
    timeToLiveAttribute: 'ttl',
  });
}

export function buildCallbackTable(scope: Construct, props: CallbackTableProps) {
  new dynamodb.TableV2(scope, props.tableName, {
    partitionKey: {
      name: 'id',
      type: AttributeType.STRING,
    },
    sortKey: {
      name: 'id_type',
      type: AttributeType.STRING,
    },
    timeToLiveAttribute: 'ttl',
    tableName: props.tableName,
    // We don't need to keep the callback table
    removalPolicy: RemovalPolicy.DESTROY,
    pointInTimeRecoverySpecification: {
      pointInTimeRecoveryEnabled: true,
    },
  });
}
