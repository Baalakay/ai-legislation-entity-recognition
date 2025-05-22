import boto3
client = boto3.client('sts')
print(client.get_caller_identity())