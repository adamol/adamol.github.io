import boto3
import os

def lambda_handler(event, context):
    client = boto3.client('rds', region_name = os.environ["DESTINATION_REGION"])

    for snapshot_arn in event['resources']:
        arn = snapshot_arn.split(':')
        snapshot_name = arn[-1]

        response = client.copy_db_snapshot(
            SourceDBSnapshotIdentifier = snapshot_arn,
            TargetDBSnapshotIdentifier = f'copy-{snapshot_name}',
            Tags=[
                {
                    'Key': 'source_region',
                    'Value': os.environ["SOURCE_REGION"]
                }
            ],
            SourceRegion = os.environ["SOURCE_REGION"],
            KmsKeyId = os.environ["DESTINATION_REGION_KMS_KEY_ID"]
        )
        print(response)