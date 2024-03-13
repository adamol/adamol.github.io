There are three types of authorization mechanisms I want to explore in this project:
- API Gateway API Keys
- Lambda Custom Authorizer
- Cognito Authorizer


## API Keys and Usage Plans
Let's start with the API Keys since they are the simplest.

```json
resource "aws_api_gateway_usage_plan" "myusageplan" {
  name = "my_usage_plan"

  api_stages {
    api_id = aws_api_gateway_rest_api.todo_api.id
    stage  = aws_api_gateway_stage.dev.stage_name
  }
}

resource "aws_api_gateway_api_key" "mykey" {
  name = "my_key"
}

resource "aws_api_gateway_usage_plan_key" "main" {
  key_id        = aws_api_gateway_api_key.mykey.id
  key_type      = "API_KEY"
  usage_plan_id = aws_api_gateway_usage_plan.myusageplan.id
}
```

API keys are linked to usage plans. Basically they define things like when to throttle an API key i.e. allowed requests per minute/second/etc. These plans are linked to your APIs and stages so you can have various different keys and basically allow external users access to your APIs (possibly for a fee).

## Activating Key for Endpoint

After you create the key there is one final part which can be tricky.

One would assume that this becomes active right away since we've linked it to our API, but we actually have to activate it on each endpoint.

```json
resource "aws_api_gateway_method" "add_todo" {
  rest_api_id   = aws_api_gateway_rest_api.todo_api.id
  resource_id   = aws_api_gateway_resource.todos_resource.id
  http_method   = "POST"

  authorization = "NONE"

  api_key_required = true
}
```
In our API GW method definition we have to update the api key field and set it to `true`. After doing this, re-deploy the API and wait a couple minutes.

Then you should be receiving errors when calling the API. These are resolved when you add an `x-api-key` header with the appropriate value, to the call.

## Custom Lambda Authorizer

The next step is to investigate using a custom Lambda function as an authorizer for our API.

Lambda Authorizers return an IAM policy to either allow or deny access to the Lambda function which the API GW wants to invoke.

```python
import base64
import json

def get_iam_policy(effect, principalId, resource):
    return {
        "principalId": principalId,
        "policyDocument": {
            "Version": '2012-10-17',
            "Statement": [
                {
                    "Action": 'execute-api:Invoke',
                    "Effect": effect,
                    "Resource": [resource]
                }
            ]
        }
    }

```

So we import required libraries and create a helper function to create our iam policies.

## Extracting the Header

```python

def lambda_handler(event, context):
    print(json.dumps(event))
    
    # Authorization: Basic <credentials>, base64 creds
    authHeader = event['authorizationToken']
    if not authHeader:
        return get_iam_policy('deny', 'unauthorized', event['methodArn'])
    
    print(f'autheader: {authHeader}')
```

The first step is to extract the "authorizationToken" from the event and return with a deny right away if it isn't present.

## Decoding the Header

```python
    decoded = base64.b64decode(authHeader.replace('Basic ', '')).decode('utf-8')
    print(f'decoded: {decoded}')
```

Then we clean up the header so the `Basic ` part is gone, and base64 decode it.

Note that after doing this we also have to decode the resulting byte array to a utf-8 string.

## Verifying the Credentials

```python

    [username, password] = decoded.split(':')

    if username != 'admin' or password != 'supersecret':
        return get_iam_policy('deny', 'unauthorized', event['methodArn'])

    return get_iam_policy('allow', username, event['methodArn'])
```

We split the string to extract username and password and to a simple check to see if a desired hardcoded value was used and return a deny or allow depending on the match.

Note that a simple improvement here would be adding the hardcoded strings to the SSM Parameter Store and injecting the values as environment variables. 

A more rigorous approach would be to use the Secrets Manager which would allos for rotating the secrets and more advanced features.

## Creating a Terraform Module for Lambda

Since we basically need to copy all the code from our initial Lambda, let's create a simple local module to reduce duplication.

```json
module "iam_for_lambda" {
  source = "../assume-role"

  role_name = "LambdaIAMRole-${var.function_name}"
  service = "lambda.amazonaws.com"
}
```

We create an IAM role using another local module. Let's get back to that one in a little bit.

## Lambda Module

```json

data "aws_iam_policy" "basic_execution_role" {
  name = "AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "basic_execution_role_attachment" {
  role       = module.iam_for_lambda.name
  policy_arn = data.aws_iam_policy.basic_execution_role.arn
}
```

Every Lambda we create will need the basic execution role, so let's just add it here right away.

```json
data "archive_file" "this" {
  type        = "zip"
  source_file = "${path.module}/../../../functions/${var.file_name}.py"
  output_path = "files/${var.file_name}-package.zip"
}

resource "aws_lambda_function" "this" {
  filename      = "files/${var.file_name}-package.zip"
  function_name = var.function_name
  role          = module.iam_for_lambda.arn
  handler       = "${var.file_name}.lambda_handler"

  source_code_hash = data.archive_file.this.output_base64sha256

  runtime = "python3.9"

  environment {
    variables = var.env_vars
  }
}
```

And this part should be familiar from the [previous project](../serverless-terraform-api/README.md).

## IAM Assume Role Module

Ok, so let's have a look at the `assume-role` module from above.

```json
data "aws_iam_policy_document" "assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = [var.service]
    }

    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "this" {
  name               = var.role_name
  assume_role_policy = data.aws_iam_policy_document.assume_role.json
}
```

Ok, it really is just the same code we've had all over the place already. Let's create one for IAM policies as well.

## IAM Policy Module

```json
data "aws_iam_policy_document" "this" {
  statement {
    effect = var.effect

    actions = var.actions

    resources = var.resources
  }
}

resource "aws_iam_policy" "this" {
  name        = var.policy_name
  path        = "/"
  policy      = data.aws_iam_policy_document.this.json
}
```

Also very simple. Just helps reduce some duplication.

## Deploying the Lambda

Now with our module in place, creating the Lambda is super simple.

```json
module "basic_auth_lambda" {
  source = "./modules/lambda"

  function_name = "ApiGatewayBasicAuthAuthorizer"
  file_name = "basic_auth_authorizer"
  env_vars = {}
}
```

We don't even need any additional policies since the Lambda just checks the header value.

## Adding Authorizer to API Gateway

We start by creating an authorizer resource in API Gateway for our Lambda.

```json
resource "aws_api_gateway_authorizer" "basic_auth" {
  name                   = "BasicAuth"
  rest_api_id            = aws_api_gateway_rest_api.todo_api.id
  authorizer_uri         = module.basic_auth_lambda.invoke_arn
  authorizer_credentials = module.invocation_role.arn
}
```

The most interesting part here are the `authorizer_credentials`. We make use of our new IAM modules to set it up, let's have a look.

```json
module "invocation_role" {
    source = "./modules/assume-role"

    role_name = "ApiGwAuthInvocation"
    service = "apigateway.amazonaws.com"
}
```

## Authorizer Role and Policy

We create a role for API GW to assume.

```json
module "invocation_policy" {
    source = "./modules/iam-policy"

    resources = [module.basic_auth_lambda.arn]
    actions = ["lambda:InvokeFunction"]
    policy_name = "ApiGwLambdaInvocationPolicy"
}

resource "aws_iam_role_policy_attachment" "api_gw_invoke_policy" {
  role       = module.invocation_role.name
  policy_arn = module.invocation_policy.arn
}
```

And we add a policy to allow it to invoke our basic auth Lambda function. 

Great, makes sense. 

## Updating API GW Resource

Now we just need one last configuration change to add the authorizer to our API resource method.

```json
resource "aws_api_gateway_method" "add_todo" {
  rest_api_id   = aws_api_gateway_rest_api.todo_api.id
  resource_id   = aws_api_gateway_resource.todos_resource.id
  http_method   = "POST"

  authorization = "CUSTOM"                                      <--- NEW
  authorizer_id = aws_api_gateway_authorizer.basic_auth.id      <--- NEW

  api_key_required = true
}
```

Before we had `authorization` set to `NONE`. Now we've added our custom authorizer.

Re-deploy the API and try it out. You will need to add basic auth credentials to your requests now.

## Cognito

Our last authorization method is using Cognito. It's a managed service so we pay for what we use with a large free tier offering and basically get an entire authorization flow out of the box with password resets etc.

```json
resource "aws_cognito_user_pool" "pool" {
  name = "todos-userpool"
}

resource "aws_cognito_user_pool_client" "client" {
  name = "client"

  user_pool_id = aws_cognito_user_pool.pool.id

  explicit_auth_flows = ["USER_PASSWORD_AUTH"]
}
```
All we need is this simple user pool and client set up for our use case. Make sure to set the explicit auth flow as `USER_PASSWORD_AUTH`.

After you create these resources, you can go ahead and create a user under the client, with a name and password.

After doing this we will need to run two commands.

```bash
aws cognito-idp initiate-auth \
    --region eu-central-1 \
    --auth-flow USER_PASSWORD_AUTH \
    --client-id <client id> \
    --auth-parameters USERNAME=<username>,PASSWORD=<password>
```

The first time you try to log in you are asked to change your credentials. You'll see a `NEW_PASSWORD_REQUIRED` in the response above as well as a Session token. Copy the Session token, you'll need it for the next command.

```bash
aws cognito-idp respond-to-auth-challenge \
  --client-id <client id> \
  --challenge-name NEW_PASSWORD_REQUIRED \
  --challenge-responses USERNAME=<username>,NEW_PASSWORD=<new password> \
  --session "$SESSION_TOKEN"
```

Here we use the token from above as validation while setting up our new password.

In the response you'll find two tokens: `IdToken` and `AccessToken`. Make sure to use the `IdToken`.

## Deploying a List Lambda

In order to try this out, let's deploy a second Lambda function.

```json
import logging
import boto3
import json
import os

session = boto3.Session(region_name = os.environ['REGION'])
dynamodb_client = session.client('dynamodb')

TABLE_NAME = os.environ['TABLE_NAME']

def lambda_handler(event, context):
    print("event: " + json.dumps(event))
    print("context: " + str(context))
    
    try:
        response = dynamodb_client.scan(TableName = TABLE_NAME)

        print(response)

        return {
            'statusCode': 201,
            'body': json.dumps(response['Items'])
        }
    except Exception as e:
        logging.error(e)
        return {
            'statusCode': 500,
            'body': 'Server Error'
        }

```

Not much going on here. We simply perform a DynamoDB scan and return.

## Deploy the List Lambda

```json
module "list_todos_lambda" {
  source = "./modules/lambda"

  function_name = "ListTodos"
  file_name = "list_todos"
  env_vars = {
      TABLE_NAME = aws_dynamodb_table.todos.name
      REGION = data.aws_region.current.name
    }
}
```
Again using our module it is super simple to add a Lambda.

## List Lambda Permissions

```json
module "dynamodb_policy_list_todos" {
  source = "./modules/iam-policy"

  actions = [
    "dynamodb:DescribeTable",
    "dynamodb:Query",
    "dynamodb:Scan"
  ]
  resources = [aws_dynamodb_table.todos.arn]
  policy_name = "ListTodosLambdaDynamoDBPolicy"
}

resource "aws_iam_role_policy_attachment" "dynamodb_policy_list_todos" {
  role       = module.list_todos_lambda.role_name
  policy_arn = module.dynamodb_policy_list_todos.arn
}
```

We add the necessary permissions for DynamoDB access.

## API GW method

```json
resource "aws_api_gateway_method" "list_todos" {
  rest_api_id   = aws_api_gateway_rest_api.todo_api.id
  resource_id   = aws_api_gateway_resource.todos_resource.id
  http_method   = "GET"

  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id

  api_key_required = true
}
```
We add a new method to our API gw for our old `todos` resource.

We make sure to still require using an api key and use `COGNITO_USER_POOLS` authorization.

## Lambda API GW Integration

```json
resource "aws_api_gateway_integration" "integration_list_todos" {
  rest_api_id             = aws_api_gateway_rest_api.todo_api.id
  resource_id             = aws_api_gateway_resource.todos_resource.id
  http_method             = aws_api_gateway_method.list_todos.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = module.list_todos_lambda.invoke_arn
}

locals {
  list_todos_method = aws_api_gateway_method.list_todos.http_method
  list_todos_path = aws_api_gateway_resource.todos_resource.path
  list_todos_invoke = "${local.rest_api_id}/*/${local.list_todos_method}${local.list_todos_path}"
}

resource "aws_lambda_permission" "apigw_lambda_list_todos" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = module.list_todos_lambda.function_name
  principal     = "apigateway.amazonaws.com"

  # More: http://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-control-access-using-iam-policies-to-invoke-api.html
  source_arn = "arn:aws:execute-api:${local.region}:${local.account_id}:${local.list_todos_invoke}"
}
```

Just like before we add an integration for our Lambda to the API GW and give API GW permission to invoke the function, using similar local variables to before.

## Try it out

Deploy the whole solution and try out the new GET endpoint.

Make sure to add the `IdToken` you copied in the `Authorization` header which Cognito uses by default.

## Conclusions

This was a bit of a long one, but a lot of fun.

In [part 3](../serverless-terraform-events/README.md) we'll be having a look at event driven work flows using EventBridge Pipes as well as DynamoDB streams, SQS and SNS.

Thanks for reading.