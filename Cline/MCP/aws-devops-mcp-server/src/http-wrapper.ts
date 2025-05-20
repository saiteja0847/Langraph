// Express HTTP wrapper for MCP server
import express from 'express';
import bodyParser from 'body-parser';
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { ListToolsRequestSchema, CallToolRequestSchema } from '@modelcontextprotocol/sdk/types.js';
import { createEc2InstanceHandler, CreateEc2InstanceArgs } from './ec2ToolHandler.js';

const mcpServer = new Server(
  {
    name: 'aws-devops-mcp-server',
    version: '0.1.0',
  },
  {
    capabilities: {
      resources: {},
      tools: {},
    },
  }
);

// Register tool handler (same as in index.ts)
mcpServer.setRequestHandler(ListToolsRequestSchema, async () => ({
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
            items: { type: 'object' },
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

// Express HTTP server
const app = express();
app.use(bodyParser.json());

app.post('/execute_tool/:tool_name', async (req, res) => {
  const toolName = req.params.tool_name;
  const args = req.body;
  try {
    if (toolName === 'create_ec2_instance') {
      const result = await createEc2InstanceHandler(args as CreateEc2InstanceArgs);
      if (result.success) {
        res.json({ status: "success", result: result.message });
      } else {
        res.json({ status: "error", error: result.message });
      }
    } else {
      res.status(400).json({ status: "error", error: `Unknown tool: ${toolName}` });
    }
  } catch (err: any) {
    res.status(500).json({ status: "error", error: err.message || String(err) });
  }
});

const PORT = process.env.PORT || 8000;
app.listen(PORT, () => {
  console.log(`MCP HTTP wrapper listening on port ${PORT}`);
});
