# Overview
With this repository I will be collecting documentation for hands on projects I do with AWS.

# Projects
- [CW Metric Filters](cloudwatch-metric-filters/README.md)
- [CW Subscription Filters](cloudwatch-subscription-filters/README.md)
- [Stopping Starting EC2 with Lambda](lambda-start-stop-ec2/README.md)
- [RDS Cross Region Copy](rds-cross-region-copy/README.md)
- [Debugging Event Driven Solutions](debugging-event-driven-solutions/README.md)
- [VPC Interface Endpoint](vpc-interface-endpoint/README.md)
- [VPC Gateway Endpoint](vpc-gateway-endpoint/README.md)
- [VPC Peering](vpc-peering/README.md)
- [Serverless API with Terraform](serverless-terraform-api/README.md)
- [Serverless API Auth with Terraform](serverless-terraform-api-auth/README.md)
- [EventBridge Pipes with Terraform](serverless-terraform-events/README.md)

# Project Ideas
- VPC Flow Logs to CloudWatch
- ECS Scheduled Task
    + https://repost.aws/questions/QUWzWBso4ySf--xcke9Ww3XQ/what-needs-to-be-done-to-make-event-bridge-invoke-a-fargate-task-when-file-added-to-s3
    + https://medium.com/@igorkachmaryk/using-terraform-to-setup-aws-eventbridge-scheduler-and-a-scheduled-ecs-task-1208ae077360
    + https://docs.aws.amazon.com/AmazonECS/latest/developerguide/scheduling_tasks.html
- EventBridge Scheduler DLQ
    + https://docs.aws.amazon.com/scheduler/latest/UserGuide/configuring-schedule-dlq.html
    + https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-rule-dlq.html
- Amazon EventBridge: Archive & Replay Events In Tandem With A Circuit-Breaker
    + https://sbrisals.medium.com/amazon-eventbridge-archive-replay-events-in-tandem-with-a-circuit-breaker-c049a4c6857f

## Maybe
- How To Build Better Orchestrations With AWS Step Functions, Task Tokens, And Amazon EventBridge!
    + https://sbrisals.medium.com/how-to-build-better-orchestrations-with-aws-step-functions-task-tokens-and-amazon-eventbridge-19a68eeda461

## Data Engineering
- DDB Glue ETL Step Functions
- DDB Incremental Load to Data Lake

## Security
- GuardDuty 
- Access Analyzer
- AWS Inspector
- Firewall Manager

## Storage
- File Gateway
- Volume Gateway
(- DataSync)

## Coding
- Golang Bubbletea TUI to Start / Stop EC2 Instances
- Python CDK

## Misc
- EC2 SQS Consumers Auto Scaling
- EC2 SQS Consumers Scale In Protection
- ALB Logs
- SSM Automation Golden AMI