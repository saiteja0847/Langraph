import { EC2Client, RunInstancesCommand, RunInstancesCommandInput, _InstanceType as AwsInstanceType } from '@aws-sdk/client-ec2';

const ec2Client = new EC2Client({
  region: process.env.AWS_DEFAULT_REGION || 'us-east-1',
});

export interface CreateEc2InstanceArgs {
  image_id: string;
  min_count: number;
  max_count: number;
  instance_type?: string;
  key_name?: string;
  security_group_ids?: string[];
  subnet_id?: string;
  user_data?: string;
  ebs_optimized?: boolean;
  monitoring_enabled?: boolean;
  availability_zone?: string;
  tags?: { [key: string]: string };
  disable_api_termination?: boolean;
  instance_initiated_shutdown_behavior?: 'stop' | 'terminate';
  block_device_mappings?: any[];
  iam_instance_profile?: any;
}

export async function createEc2InstanceHandler(args: CreateEc2InstanceArgs) {
  const params: RunInstancesCommandInput = {
    ImageId: args.image_id,
    MinCount: args.min_count,
    MaxCount: args.max_count,
    InstanceType: args.instance_type as AwsInstanceType || 't2.micro',
    KeyName: args.key_name,
    SecurityGroupIds: args.security_group_ids,
    SubnetId: args.subnet_id,
    UserData: args.user_data ? Buffer.from(args.user_data).toString('base64') : undefined,
    EbsOptimized: args.ebs_optimized,
    Monitoring: args.monitoring_enabled !== undefined ? { Enabled: args.monitoring_enabled } : undefined,
    Placement: args.availability_zone ? { AvailabilityZone: args.availability_zone } : undefined,
    DisableApiTermination: args.disable_api_termination,
    InstanceInitiatedShutdownBehavior: args.instance_initiated_shutdown_behavior,
    BlockDeviceMappings: args.block_device_mappings,
    IamInstanceProfile: args.iam_instance_profile,
  };
  if (args.tags) {
    params.TagSpecifications = [{
      ResourceType: "instance",
      Tags: Object.entries(args.tags).map(([Key, Value]) => ({ Key, Value })),
    }];
  }
  try {
    const command = new RunInstancesCommand(params);
    const response = await ec2Client.send(command);
    const instanceIds = response.Instances?.map(inst => inst.InstanceId).join(', ');
    return {
      success: true,
      message: `EC2 instance(s) launched successfully. Instance IDs: ${instanceIds}`,
    };
  } catch (error: any) {
    return {
      success: false,
      message: `Error launching EC2 instance: ${error.message || String(error)}`,
    };
  }
}
