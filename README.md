# Overview
With this repository I will be collecting documentation for hands on projects I do with AWS.

# Why are the projects using the AWS CLI?
1. I enjoy working with the CLI
2. Normally I would use IaC with either Terraform or CloudFormation, but since these are smaller one-time projects with no other contributors than myself, I am just a bit faster using the CLI.
3. The CLI still provides reproducibility just like IaC, and should be pretty easy to translate to IaC if so desired.
4. Using the console is too manual and not easily reproducible.

# Projects
- [CW Metric Filters](cloudwatch-metric-filters/README.md)
- [CW Subscription Filters](cloudwatch-subscription-filters/README.md)
- [Stopping Starting EC2 with Lambda](lambda-start-stop-ec2/README.md)
- [RDS Cross Region Copy](rds-cross-region-copy/README.md)
- [Debugging Event Driven Solutions](debugging-event-driven-solutions/README.md)
- VPC Flow Logs to CloudWatch
- VPC Interface Endpoint SQS
- VPC Gateway Endpoint S3/DDB
- VPC Peering
- File Gateway
- Volume Gateway
- DataSync
- DDB Glue ETL Step Functions
- DDB Incremental Load to Data Lake
- EC2 SQS Consumers Auto Scaling
- EC2 SQS Consumers Scale In Protection
- ALB Logs
- GuardDuty
- Access Analyzer
- AWS Inspector
- SSM Automation Golden AMI