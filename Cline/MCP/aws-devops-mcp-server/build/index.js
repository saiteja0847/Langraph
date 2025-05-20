#!/usr/bin/env node
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { CallToolRequestSchema, ErrorCode, ListToolsRequestSchema, McpError, } from '@modelcontextprotocol/sdk/types.js';
import { createEc2InstanceHandler } from './ec2ToolHandler.js'; // Import shared handler
// Removed EC2Client and AWS SDK specific imports as they are now in ec2ToolHandler.ts
// Type guard for CreateEc2InstanceArgs (can be kept or simplified if validation is done in handler)
function isValidCreateEc2InstanceArgs(args) {
    return (typeof args === 'object' &&
        args !== null &&
        typeof args.image_id === 'string' &&
        typeof args.min_count === 'number' &&
        typeof args.max_count === 'number' &&
        // Optional: Add more checks if needed, or rely on handler's type safety
        true);
}
class AwsDevOpsServer {
    constructor() {
        this.server = new Server({
            name: 'aws-devops-mcp-server',
            version: '0.1.0',
        }, {
            capabilities: {
                resources: {}, // No resources defined for now
                tools: {},
            },
        });
        this.setupToolHandlers();
        this.server.onerror = (error) => console.error('[MCP Error]', error);
        process.on('SIGINT', async () => {
            await this.server.close();
            process.exit(0);
        });
    }
    setupToolHandlers() {
        this.server.setRequestHandler(ListToolsRequestSchema, async () => ({
            tools: [
                {
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
                                items: {
                                    type: 'object',
                                    // Define properties for BlockDeviceMapping if needed, or keep it generic
                                },
                                description: 'Define EBS volumes. List of mappings, e.g., [{"DeviceName": "/dev/sda1", "Ebs": {"VolumeSize": 30, "VolumeType": "gp3"}}]',
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
                },
            ],
        }));
        this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
            if (request.params.name !== 'create_ec2_instance') {
                throw new McpError(ErrorCode.MethodNotFound, `Unknown tool: ${request.params.name}`);
            }
            if (!isValidCreateEc2InstanceArgs(request.params.arguments)) {
                throw new McpError(ErrorCode.InvalidParams, 'Invalid arguments for create_ec2_instance');
            }
            const args = request.params.arguments;
            try {
                const result = await createEc2InstanceHandler(args);
                return {
                    content: [
                        {
                            type: 'text',
                            text: result.message,
                        },
                    ],
                    isError: !result.success,
                };
            }
            catch (error) {
                console.error("Error in create_ec2_instance tool handler:", error);
                return {
                    content: [
                        {
                            type: 'text',
                            text: `Internal server error: ${error.message || String(error)}`,
                        },
                    ],
                    isError: true,
                };
            }
        });
    }
    async run() {
        const transport = new StdioServerTransport();
        await this.server.connect(transport);
        console.error('AWS DevOps MCP server running on stdio');
    }
}
const server = new AwsDevOpsServer();
server.run().catch(error => {
    console.error('Failed to run AWS DevOps MCP server:', error);
    process.exit(1); // Exit if server fails to run
});
