The original idea of this project was to explore EventBridge Pipes. But in order to test it out a bit and set up an example that felt real-world, I also added an SQS queue which subscribes to the SNS topic and a Lambda which is invoked by SQS.

## DynamoDB Stream

Let's start off by adding the stream to DynamoDB. We simply need to update the current table with two new fields.

```json
resource "aws_dynamodb_table" "todos" {
  ...

  stream_enabled   = true                   <--- NEW
  stream_view_type = "NEW_AND_OLD_IMAGES"   <--- NEW
}
```

And now we get started with the EventBridge Pipe.

## EventBridge Pipe IAM Role

The largest part of the code will be for IAM roles and policies.

```json
#### IAM ROLE ####
module "pipe_role" {
  source = "./modules/assume-role"

  role_name = "TodosEBPipe"
  service = "pipes.amazonaws.com"
}
```
We use our module from the previous project to create a role for EB Pipes to assume.

## EventBridge Pipe Source Policy
```json
module "pipe_source_policy" {
  source = "./modules/iam-policy"

  resources = ["*"]
  actions = [
          "dynamodb:DescribeStream",
          "dynamodb:GetRecords",
          "dynamodb:GetShardIterator",
          "dynamodb:ListStreams",
          "events:PutEvents"
        ]
  policy_name = "TodosEBPipe-SourcePolicy"
}

resource "aws_iam_role_policy_attachment" "pipe_source_policy_attachment" {
  role       = module.pipe_role.name
  policy_arn = module.pipe_source_policy.arn
}
```

We add the required permissions for EB Pipes to read from our DynamoDB Stream.

## EventBridge Pipe Target Policy

```json
resource "aws_sns_topic" "target" {
  name = "serverless-eventdriven-topic"
}
```

We create a super basic SNS topic.

```json
module "pipe_target_policy" {
  source = "./modules/iam-policy"

  resources = ["*"]
  actions = ["sns:Publish"]
  policy_name = "TodosEBPipe-TargetPolicy"
}

resource "aws_iam_role_policy_attachment" "pipe_target_policy_attachment" {
  role       = module.pipe_role.name
  policy_arn = module.pipe_target_policy.arn
}
```

And we provide our IAM Role access to publish to the topic.

## EventBridge Pipe

```json
resource "aws_pipes_pipe" "this" {
  name     = "TodosApiPipe"
  role_arn = module.pipe_role.arn
  source   = aws_dynamodb_table.todos.stream_arn
  target   = aws_sns_topic.target.arn

  source_parameters {
    dynamodb_stream_parameters {
      batch_size        = 1
      starting_position = "LATEST"
    }
  }
}
```

We configure our pipe between our source and target and voila the data is being passed from one to the other.

The only configuration to note are the source parameters. We set the batch size to 1, but in a production usecase batching could of course provide better performance. And `starting_position` as `LATEST` makes sure we only read new entries.

## SQS Queue

```json
resource "aws_sqs_queue" "queue" {
  name = "serverless-eventdriven-queue"
}

resource "aws_sns_topic_subscription" "user_updates_sqs_target" {
  topic_arn = aws_sns_topic.target.arn
  protocol  = "sqs"
  endpoint  = aws_sqs_queue.queue.arn
}
```

We create an SQS queue and subscribe it to our SNS topic.

## Queue Policy

```json
data "aws_iam_policy_document" "allow_sns_queue_access" {
  statement {
    sid    = "AllowSNSToSendMessagesToQueue"
    effect = "Allow"

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.queue.arn]

    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [aws_sns_topic.target.arn]
    }
  }
}

resource "aws_sqs_queue_policy" "this" {
  queue_url = aws_sqs_queue.queue.id
  policy    = data.aws_iam_policy_document.allow_sns_queue_access.json
}
```

We create an SQS queue policy to allow SNS to send messages to it.

## SQS Event Source Mapping

```json
resource "aws_lambda_event_source_mapping" "this" {
  event_source_arn = aws_sqs_queue.queue.arn
  function_name    = module.sqs_handler_lambda.arn
}
```

And as a final step here we add an Event Source Mapping to trigger a new Lambda function when a message is added to the SQS queue.

This architecture has enabled us to process the events asynchronously, while also allowing other services to be triggered by the SNS topic in parallel if they want.

Let's have a look at the Lambda function.

## Lambda Function

```python
import json

def lambda_handler(event, context):
    print(json.dumps(event))

    payload = json.loads(event['Records'][0]['body'])
    print(json.dumps(payload))

    message = json.loads(payload['Message'])
    print(json.dumps(message))

```

By far our simplest function. We simply parse the message and dump is as json.

Note that the message is quite nested. This is because both the DynamoDB Stream and SNS add metadata to the entry.

## Lambda Deployment

Again our Lambda function is super simple with our helper module.

```json
module "sqs_handler_lambda" {
  source = "./modules/lambda"

  function_name = "TodoSQSHandler"
  file_name = "sqs_handler"
  env_vars = {}
}
```

But we still need an additional IAM Policy to receive messages from SQS.

```json
module "sqs_policy" {
  source = "./modules/iam-policy"

  actions = [
    "sqs:ReceiveMessage",
    "sqs:DeleteMessage",
    "sqs:GetQueueAttributes"
  ]
  resources = [aws_sqs_queue.queue.arn]
  policy_name = "TodoSQSHandlerLambdaSQSPolicy"
}

resource "aws_iam_role_policy_attachment" "sqs_policy" {
  role       = module.sqs_handler_lambda.role_name
  policy_arn = module.sqs_policy.arn
}
```

And we're all done.

## Test it Out

Simply deploy the solution and test it out again by adding a new todo using the API GW endpoint.

You should see a CloudWatch log entry produced from the final Lambda function with the event data.

## Conclusions

This project series has been a ton of fun. 

We've explored a ton of serverless services and even had a look at the value of small re-usable terraform modules to minimize code duplication.

I really enjoy such simple to maintain opinionated modules.

It is quite similar to extracting duplicated logic in a class or function in my opinion.

If you need the same modules in other projects you can simply extract them to a separate project and include it in both. Note that this will require some type of terraform registry though.