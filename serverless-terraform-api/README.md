The goal of this project is to set up a simple Lambda API with DynamoDB and API Gateway using Terraform.

## IAM Role for Lambda
Let's start with the Lambda IAM Role.

```json
data "aws_iam_policy_document" "assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "iam_for_lambda" {
  name               = "iam_for_lambda"
  assume_role_policy = data.aws_iam_policy_document.assume_role.json
}
```

Of course there's nothing special here. Let's add the basic execution role.

## Basic Execution Role

```json
data "aws_iam_policy" "basic_execution_role" {
  name = "AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "basic_execution_role_attachment" {
  role       = aws_iam_role.iam_for_lambda.name
  policy_arn = data.aws_iam_policy.basic_execution_role.arn
}
```

This role gives the Lambda permissions to interact with CloudWatch. Both to create a log group and put the logs.

But our Lambda will also need to interact with a dynamodb table. Let's add the table before adding the permissions.

## Creating the DynamoDB Table

```json
resource "aws_dynamodb_table" "todos" {
  name           = "Todos"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "Id"

  attribute {
    name = "Id"
    type = "S"
  }
}
```

A very simple pay per request table. You can of course provision capacity to be maybe 1-5 RCUs, that's up to you.

Note the `hash_key` is called simply Id. A perhaps more dynamodb-esque naming would be simply `PK`. This is generally a good idea when you are considering a multi table design, but it doesn't matter too much for our example.

## DynamoDB Permissions for Lambda

```json
data "aws_iam_policy_document" "dynamodb_policy" {
  statement {
    effect = "Allow"

    actions = [
      "dynamodb:PutItem",
    ]

    resources = [aws_dynamodb_table.todos.arn]
  }
}

resource "aws_iam_policy" "dynamodb_policy" {
  name        = "dynamodb_policy"
  path        = "/"
  description = "IAM policy for dynamodb access from a lambda"
  policy      = data.aws_iam_policy_document.dynamodb_policy.json
}

resource "aws_iam_role_policy_attachment" "dynamodb_policy" {
  role       = aws_iam_role.iam_for_lambda.name
  policy_arn = aws_iam_policy.dynamodb_policy.arn
}
```

Our Lambda will just be adding todos, so we can get away with a single action in the IAM policy.

## Lambda Function

Now we're ready to set up our lambda function.

```json
data "archive_file" "lambda" {
  type        = "zip"
  source_file = "${path.module}/../functions/add_todo.py"
  output_path = "lambda_api-package.zip"
}

resource "aws_lambda_function" "add_todo" {
  filename      = "lambda_api-package.zip"
  function_name = "AddTodo"
  role          = aws_iam_role.iam_for_lambda.arn
  handler       = "add_todo.lambda_handler"

  source_code_hash = data.archive_file.lambda.output_base64sha256

  runtime = "python3.9"

  environment {
    variables = {
      TABLE_NAME = aws_dynamodb_table.todos.name
      REGION = data.aws_region.current.name
    }
  }
}
```

Importantly we zip our function in order to deploy it. This is a bit more tedious when you have dependencies to work with. Then you would need to install the dependencies as well and zip up all the contents together with your function. But yeah it's basically the same process in the end of uploading a zip file.

Other than that, we make sure to use the `source_code_hash` so we only re-deploy our Lambda when our code changes, and we also pass in the necessary environment variables.

## DATA SOURCES

A small note on two data sources that have been added.

```json
data "aws_region" "current" {}

data "aws_caller_identity" "current" {}
```

These are available in all terraform projects and come in real handy. We used the region one above and will need `aws_caller_identity` later.

## LAMBDA CODE

```python
import logging
import boto3
import json
import uuid
import os

session = boto3.Session(region_name = os.environ['REGION'])
dynamodb_client = session.client('dynamodb')

TABLE_NAME = os.environ['TABLE_NAME']

def lambda_handler(event, context):
    print("event: " + json.dumps(event))
    print("context: " + str(context))

    payload = json.loads(event['body'])

```
Importing required libraries, starting a DynamoDB client using the boto3 Session object and parsing the request payload from the event.

```python

    try:
        response = dynamodb_client.put_item(
            TableName = TABLE_NAME,
            Item = {
                'Id': {
                    'S': str(uuid.uuid4())
                },
                'Description': {
                    'S': payload['description']
                }
            }
        )
```
We use the DynamoDB client to add an item to the table with the description from the payload.
```python
        print(response)

        return {
            'statusCode': 201,
        }
    except Exception as e:
        logging.error(e)
        return {
            'statusCode': 500,
            'body': 'Server Error'
        }
```
Depending on success of request we return a valid status code as a response.

Ok great. With all that setup we are ready for the last piece: API Gateway.

## API Endpoint with API Gateway

First off we need a rest api entity.

```json
resource "aws_api_gateway_rest_api" "todo_api" {
  name = "todo-api"

  endpoint_configuration {
    types = ["REGIONAL"]
  }
}
```

API Gateway Rest APIs offer more feature than HTTP APIs, while HTTP APIs are cheaper.

We will be using access keys in a follow up project though, and this is only supported by rest APIs.

We also make sure it's of type `REGIONAL`. The other options would be 
- `EDGE_OPTIMIZED`: which integrates with CloudFront Points of Presence
- `PRIVATE`: which is for use within a VPC

```json
resource "aws_api_gateway_resource" "todos_resource" {
  rest_api_id = aws_api_gateway_rest_api.todo_api.id
  parent_id   = aws_api_gateway_rest_api.todo_api.root_resource_id
  path_part   = "todos"
}

resource "aws_api_gateway_method" "add_todo" {
  rest_api_id   = aws_api_gateway_rest_api.todo_api.id
  resource_id   = aws_api_gateway_resource.todos_resource.id
  http_method   = "POST"
  authorization = "NONE"

  api_key_required = false
}
```

API GW REST APIs use typical terminology like resources and methods. We add a ´todos´ resource and a method of `POST` to add our todos.

For now the `api_key_required` will be false and `authorization` is `NONE`, but we will be changing this in the follow up project.

## API GW DEPLOYMENT

```json
resource "aws_api_gateway_deployment" "deployment" {
  rest_api_id = aws_api_gateway_rest_api.todo_api.id

  triggers = {
    redeployment = sha1(jsonencode(aws_api_gateway_rest_api.todo_api.body))
  }

  lifecycle {
    create_before_destroy = true
  }
}
```

The deployment resource helps us automatically deploy our API when we add methods or resources. There are still times when you have to manually deploy though. For instance when adding an API Key.

```json
resource "aws_api_gateway_stage" "dev" {
  deployment_id = aws_api_gateway_deployment.deployment.id
  rest_api_id   = aws_api_gateway_rest_api.todo_api.id
  stage_name    = "dev"
}
```

API Gateway is made to be used with various stages and here the `dev` stage is linked with our deployment above.

In real world use cases you would pass in an environment variable from terraform here and have a pipeline first building dev and staging environments. And after some approval process, the deployment goes on to production.

## Connect API Gateway to Lambda

The last piece of the puzzle is linking our API Gateway with our Lambda function. For that we use an API GW Integration.

```json
resource "aws_api_gateway_integration" "integration" {
  rest_api_id             = aws_api_gateway_rest_api.todo_api.id
  resource_id             = aws_api_gateway_resource.todos_resource.id
  http_method             = aws_api_gateway_method.add_todo.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.add_todo.invoke_arn
}

locals {
  rest_api_id = aws_api_gateway_rest_api.todo_api.id
}

locals {
  region = data.aws_region.current.name
  account_id = data.aws_caller_identity.current.account_id
}

locals {
  add_todo_method = aws_api_gateway_method.add_todo.http_method
  add_todo_path = aws_api_gateway_resource.todos_resource.path
  add_todo_invoke = "${local.rest_api_id}/*/${local.add_todo_method}${local.add_todo_path}"
}

resource "aws_lambda_permission" "apigw_lambda" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.add_todo.function_name
  principal     = "apigateway.amazonaws.com"

  # More: http://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-control-access-using-iam-policies-to-invoke-api.html
  source_arn = "arn:aws:execute-api:${local.region}:${local.account_id}:${local.add_todo_invoke}"
}
```

The integration has two parts: the integration itself and the permissions required.

For the permissions we make sure to set the source arn to avoid the confused deputy problem, which is a common security vulnerability in AWS.

In order to make the ARN readable I made use of some local terraform variables which hopefully make sense.

## Conclusions

That's all for this initial project, but it continues in [part 2](../serverless-terraform-api-auth/) where we set up authorization.
