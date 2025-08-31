import * as s3 from 'aws-cdk-lib/aws-s3';
import { Construct } from 'constructs';
import { Bucket } from 'aws-cdk-lib/aws-s3';
import { Duration } from 'aws-cdk-lib';
import { PAYLOADS_KEY_PREFIX } from '../constants';

function addPayloadsLifeCycleRuleToBucket(bucket: Bucket): void {
  bucket.addLifecycleRule({
    id: 'DeletePayloadJsonsAfterSixMonths',
    enabled: true,
    expiration: Duration.days(30), // Delete objects older than 1 month
    prefix: PAYLOADS_KEY_PREFIX, // Apply to objects with the 'analysis-payloads/' prefix
  });
}

function createS3Bucket(scope: Construct, bucketName: string): Bucket {
  // This is a placeholder function that simulates creating an S3 bucket.
  // In a real implementation, you would use the AWS SDK to create the bucket.
  return new s3.Bucket(scope, 'icav2-wes-artefacts-bucket', {
    bucketName: bucketName,
    blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
  });
}

export function createArtefactsBucket(scope: Construct, bucketName: string): Bucket {
  const s3Bucket = createS3Bucket(scope, bucketName);

  // Add lifecycle rules to the bucket
  addPayloadsLifeCycleRuleToBucket(s3Bucket);
  return s3Bucket;
}
