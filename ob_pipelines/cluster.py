import boto3
import base64
import time

import click
from ob_pipelines.config import cfg

# Connect to AWS clients
session = boto3.Session(profile_name=cfg['AWS_PROFILE'])
batch_client = session.client('batch')
ec2_client = session.client('ec2')


def build_launch_spec(cfg):
    """Build launch specification that joins the ECS cluster tied to this compute env"""
    compute_envs = batch_client.describe_compute_environments(computeEnvironments=[cfg['COMPUTE_ENV']])
    ecs_arn = compute_envs['computeEnvironments'][0]['ecsClusterArn']
    ecs_name = ecs_arn.split('cluster/')[-1]

    return {
        'ImageId': cfg['IMAGE_ID'],
        'KeyName': cfg['KEY_NAME'],
        'SecurityGroups': [
            {
                'GroupId': cfg['SECURITY_GROUP']
            },
        ],
        'UserData': base64.b64encode('\n'.join([
            '#!/bin/bash',
            'echo ECS_CLUSTER=%s >> /etc/ecs/ecs.config' % ecs_name,

            '# Stop Docker before mounting new drives',
            'docker ps',
            'service docker stop',

            '# Mount ephemeral 0 and link to /scratch',
            'mkdir -p /media/ephemeral0',
            'mount /dev/xvdb /media/ephemeral0',
            'mkdir -p /media/ephemeral0/scratch',
            'chmod 777 /media/ephemeral0/scratch',
            'ln --symbolic /media/ephemeral0/scratch /scratch',

            '# Mount ephemeral 1 and link to /reference',
            'mkdir -p /media/ephemeral1',
            'mount /dev/xvdc /media/ephemeral1',
            'mkdir -p /media/ephemeral1/reference',
            'chmod 777 /media/ephemeral1/reference',
            'ln --symbolic /media/ephemeral1/reference /reference',

            '# Mount EBS',
            'mkdir -p /media/ebs',
            'mount /dev/xvdm /media/ebs',

            '# Restart Docker',
            'service docker start',

            '# Sync reference data and copy to ephemeral',
            'sudo yum install -y python-pip',
            'sudo python-pip install awscli',
            '/usr/local/bin/aws s3 sync s3://outlierbio/reference/ /mnt/reference/',
            'cp -R /mnt/reference/ /reference/'
        ]).encode('ascii')).decode('ascii'),
        'InstanceType': 'c3.8xlarge',
        'BlockDeviceMappings': [
            {
                'VirtualName': 'reference',
                'DeviceName': '/dev/xvdm',
                'Ebs': {
                    'SnapshotId': cfg['REFERENCE_SNAPSHOT'],
                    'VolumeSize': 500,
                    'DeleteOnTermination': True,
                    'VolumeType': 'io1',
                    'Encrypted': False,
                    'Iops': 5000
                }
            },
            {
               "VirtualName" : "ephemeral0",
               "DeviceName"  : "/dev/xvdb"
            },
            {
               "VirtualName" : "ephemeral1",
               "DeviceName"  : "/dev/xvdc",
            },
        ],
        'Monitoring': {
            'Enabled': True
        },
        'SubnetId': ','.join(cfg['SUBNETS']),
        'IamInstanceProfile': {
            'Name': 'ecsInstanceRole',
        },
        'EbsOptimized': True
    }


def create_compute_env(cfg):
    """Create compute environment"""
    response = batch_client.create_compute_environment(
            computeEnvironmentName=cfg['COMPUTE_ENV'],
            serviceRole=cfg['BATCH_SERVICE_ROLE'],
            type='UNMANAGED',
            state='ENABLED'
        )

    time.sleep(5) # Give a little space, just in case the queue is created next

    return response


def request_spot_fleet(launch_spec, price=cfg['SPOT_PRICE'], capacity=cfg['TARGET_CAPACITY'], role=cfg['SPOT_FLEET_ROLE']):
    """Request spot fleet with this launch spec"""
    return ec2_client.request_spot_fleet(
         SpotFleetRequestConfig={
             'SpotPrice': price,
             'TargetCapacity': capacity,
             'TerminateInstancesWithExpiration': True,
             'IamFleetRole': role,
             'LaunchSpecifications': [launch_spec]
         }
     )


def create_job_queue(cfg):
    """Create job queue"""
    compute_environment_order = [{
        'computeEnvironment': cfg['COMPUTE_ENV'],
        'order': 1
    }]

    return batch_client.create_job_queue(
        computeEnvironmentOrder=compute_environment_order,
        jobQueueName=cfg['QUEUE_NAME'],
        priority=1,
        state='ENABLED'
    )


## Autoscaling ###############################

# as_client = boto3.client('autoscaling')
# lc_name = COMPUTE_ENV + '-launch-config'
# as_name = COMPUTE_ENV + '-autoscaling'
# response = as_client.create_launch_configuration(
#     LaunchConfigurationName=lc_name,
#     ImageId=IMAGE_ID,
#     KeyName=KEY_NAME,
#     SecurityGroups=[SECURITY_GROUP],
#     InstanceType=INSTANCE_TYPE,
#     InstanceMonitoring={
#         'Enabled': True
#     },
#     IamInstanceProfile='ecsInstanceRole'
# )

# response = as_client.create_auto_scaling_group(
#     AutoScalingGroupName=as_name,
#     LaunchConfigurationName=lc_name,
#     MinSize=0,
#     MaxSize=5,
#     DesiredCapacity=0,
#     VPCZoneIdentifier='subnet-16344a3b'
# )

## end autoscaling ############################


@click.group()
def cli():
    pass

@cli.command()
@click.argument('capacity', default=cfg['TARGET_CAPACITY'])
def start(capacity):
    spec = build_launch_spec(cfg)
    request_spot_fleet(spec, capacity=capacity)

@cli.command()
def shutdown():
    response = ec2_client.describe_spot_fleet_requests()
    spot_fleet_ids = [c['SpotFleetRequestId'] 
                      for c in response['SpotFleetRequestConfigs']
                      if c['SpotFleetRequestState'] == 'active']
    ec2_client.cancel_spot_fleet_requests(
        SpotFleetRequestIds=spot_fleet_ids,
        TerminateInstances=True
    )


if __name__ == '__main__':
    cli()

