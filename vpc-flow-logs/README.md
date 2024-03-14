# Creating Networks and EC2 Instances

We've already set up VPCs and Subnets and launched EC2 instances using the CLI in a couple of projects so let's do something a bit different this time. We'll be deploying a CloudFormation template and make use of nested stacks to reduce duplication.

We have the following CloudFormation files:
- [Root Stack](stack.yml)
- [Network Template](network-template.yml)
- [IAM Template](iam-template.yml)

Take a minute to skim through the resources. 

The Network Template sets up a VPC with an Internet Gateway attached and a single Subnet.

The IAM Template creates an instance profile to allow us to connect to EC2 using the SSM Session Manager.

In the root stack we create two instances of the network template: NetworkA and Network B. And we also launch an EC2 instance into each network using the Instance Profile from the IAM Template.

```yaml
  NetworkA:
    Type: AWS::CloudFormation::Stack
    Properties:
      TemplateURL: 'network-template.yml'
      Parameters:
        VpcCidr: 10.16.0.0/16
        SubnetCidr: 10.16.0.0/20
        TagPostfix: A
  InstanceA: 
    Type: AWS::EC2::Instance
    Properties: 
      ImageId: !Ref LatestAmiId
      SubnetId: !GetAtt NetworkA.Output.SubnetId
      IamInstanceProfile: !GetAtt InstanceProfile.Outputs.Name
      Tags:
        - Key: Name
          Value: InstanceA
```

# Create IAM Role for Flow Logs

```bash
echo '{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "vpc-flow-logs.amazonaws.com"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "aws:SourceAccount": "<account_id>"
        },
        "ArnLike": {
          "aws:SourceArn": "arn:aws:ec2:<region>:<account_id>:vpc-flow-log/*"
        }
      }
    }
  ]
}' > VpcFlowLogsRole.json

echo '{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams"
      ],
      "Resource": "*"
    }
  ]
}' > VpcFlowLogsPolicy.json
```

# Manual Testing
1st: 2 VPCs, 2 Instances, no SG access

ping target fails
ping 8.8.8.8 succeeds (IGW)

2nd: Correct SG in target to allow ping

ping target succeeds

3rd: Add NACL outbound

ping target fails
connect target -> ping 8.8.8.8 fails

# Log Insights
Filter for traffic to 8.8.8.8
From source ip / target ip

```
stats sum(packets) as packetsTransferred by srcAddr, dstAddr
    | sort packetsTransferred  desc
    | limit 15
```

```
filter isIpv4InSubnet(srcAddr, "192.0.2.0/24")
    | stats sum(bytes) as bytesTransferred by dstAddr
    | sort bytesTransferred desc
    | limit 15
```

```
fields @timestamp, srcAddr, dstAddr, srcPort, dstPort, protocol, bytes 
| filter logStream = 'vpc-flow-logs' and interfaceId = 'eni-0123456789abcdef0' 
| sort @timestamp desc 
| dedup srcAddr, dstAddr, srcPort, dstPort, protocol 
| limit 20
```