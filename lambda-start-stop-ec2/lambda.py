import boto3

client = boto3.client('ec2')
TAG_KEY = 'Scheduled'
TAG_VALUE = 'OfficeHours'

def start_instances(instance_ids):
    print('Starting instances...')
    client.start_instances(InstanceIds=instance_ids)

    print('Waiting for instances to start...')
    waiter = client.get_waiter('instance_running')
    waiter.wait(InstanceIds=instance_ids)
    print('Instances started successfully')

def stop_instances(instance_ids):
    print('Stopping instances...')
    client.stop_instances(InstanceIds=instance_ids)

    print('Waiting for instances to stop...')
    waiter = client.get_waiter('instance_stopped')
    waiter.wait(InstanceIds=instance_ids)
    print('Instances stopped successfully')

def lambda_handler(event, context):
    print(event)
    print(context)

    custom_filter = [{
        'Name':f'tag:{TAG_KEY}', 
        'Values': [TAG_VALUE]
    }]
    
    response = client.describe_instances(Filters=custom_filter)

    instance_ids = []
    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            instance_ids.append(instance['InstanceId'])

    if not instance_ids:
        print(f'Found no instance ids with tag {TAG_KEY}={TAG_VALUE}')
        exit()

    print(f"Found instance ids {','.join(instance_ids)} with tag {TAG_KEY}={TAG_VALUE}")

    if event['Action'] == 'Start':
        start_instances(instance_ids)
    elif event['Action'] == 'Stop':
        stop_instances(instance_ids)
    else:
        print(f'Unknown action {event["Action"]} provided by event.')
