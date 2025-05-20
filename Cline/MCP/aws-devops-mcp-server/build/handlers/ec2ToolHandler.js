import { EC2Client, RunInstancesCommand } from '@aws-sdk/client-ec2';
const ec2Client = new EC2Client({
    region: process.env.AWS_DEFAULT_REGION || 'us-east-1',
});
export async function createEc2InstanceHandler(args) {
    const params = {
        ImageId: args.image_id,
        MinCount: args.min_count,
        MaxCount: args.max_count,
        InstanceType: args.instance_type || 't2.micro',
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
                ResourceType: 'instance',
                Tags: Object.entries(args.tags).map(([Key, Value]) => ({ Key, Value })),
            }];
    }
    try {
        const command = new RunInstancesCommand(params);
        const response = await ec2Client.send(command);
        const instanceIds = response.Instances?.map(inst => inst.InstanceId).join(', ');
        return { success: true, message: `EC2 instance(s) launched successfully. Instance IDs: ${instanceIds}` };
    }
    catch (error) {
        return { success: false, message: `Error launching EC2 instance: ${error.message || String(error)}` };
    }
}
export function isValidCreateEc2InstanceArgs(args) {
    return (typeof args === 'object' &&
        args !== null &&
        typeof args.image_id === 'string' &&
        typeof args.min_count === 'number' &&
        typeof args.max_count === 'number');
}
export const ec2ToolDefinition = {
    name: 'create_ec2_instance',
    description: 'Creates an AWS EC2 instance based on the provided parameters. This tool is used to provision virtual servers in AWS cloud. If the user specifies an "instance name", interpret this as a request to set a tag with the key "Name" and the value as the specified name.',
    inputSchema: {
        type: 'object',
        properties: {
            image_id: { type: 'string', description: 'The ID of the AMI (Amazon Machine Image) to use for the instance. Required.' },
            min_count: { type: 'integer', description: 'The minimum number of instances to launch. Usually 1. Required.' },
            max_count: { type: 'integer', description: 'The maximum number of instances to launch. Usually 1. Required.' },
            instance_type: { type: 'string', default: 't2.micro', description: 'The type of instance to launch, e.g., "t2.micro", "m5.large".' },
            key_name: { type: 'string', description: 'The name of the key pair for SSH access.' },
            security_group_ids: { type: 'array', items: { type: 'string' }, description: 'A list of security group IDs.' },
            subnet_id: { type: 'string', description: 'The ID of the subnet to launch the instance into.' },
            user_data: { type: 'string', description: 'User data to make available to the instance.' },
            ebs_optimized: { type: 'boolean', default: false, description: 'Whether the instance is optimized for Amazon EBS I/O.' },
            monitoring_enabled: { type: 'boolean', default: false, description: 'Enables detailed monitoring for the instance.' },
            availability_zone: { type: 'string', description: 'The Availability Zone to launch the instance into, e.g., "us-east-1a".' },
            tags: {
                type: 'object',
                additionalProperties: { type: 'string' },
                description: 'A dictionary of key-value pairs to assign as tags. For instance name, use key "Name". Example: {"Name": "MyServer", "Environment": "Dev"}'
            },
            disable_api_termination: { type: 'boolean', default: false, description: 'If true, enables instance termination protection.' },
            instance_initiated_shutdown_behavior: { type: 'string', enum: ['stop', 'terminate'], default: 'stop', description: 'Whether the instance should "stop" or "terminate" when shut down from within the OS.' },
            block_device_mappings: {
                type: 'array',
                items: { type: 'object' },
                description: 'Define EBS volumes. List of mappings, e.g., [{"DeviceName": "/dev/sda1", "Ebs": {"VolumeSize": 30, "VolumeType": "gp3"}}]'
            },
            iam_instance_profile: {
                type: 'object',
                properties: {
                    Arn: { type: 'string' },
                    Name: { type: 'string' },
                },
                description: 'IAM instance profile. Provide as {"Arn": "arn:aws:iam::ACCOUNT:instance-profile/PROFILE_NAME"} or {"Name": "PROFILE_NAME"}.',
            },
        },
        required: ['image_id', 'min_count', 'max_count'],
    },
    handler: createEc2InstanceHandler,
    isValidArgs: isValidCreateEc2InstanceArgs,
};
