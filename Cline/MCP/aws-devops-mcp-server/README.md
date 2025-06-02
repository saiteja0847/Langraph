# AWS DevOps MCP Server

This MCP server provides AWS DevOps capabilities to AI agents through the Model Context Protocol (MCP).

## Overview

The AWS DevOps MCP server exposes a set of tools that allow AI agents to manage AWS resources programmatically. It acts as a bridge between AI agents and the AWS SDK, providing a standardized interface for operations like creating EC2 instances or S3 buckets.

## Features

Currently, the server provides tools for:

- **EC2 Management**: Creating EC2 instances with customizable parameters
- **S3 Management**: Creating S3 buckets with region and ACL settings

## Architecture

The server is built using TypeScript and the AWS SDK v3. It follows the Model Context Protocol specification for tools and resources, enabling any MCP-compatible AI agent to use its capabilities.

Key components:

- `index.ts`: Server entry point and MCP protocol handling
- `toolRegistry.ts`: Registry of all available tools
- `handlers/`: Individual tool handlers for each AWS service
  - `ec2ToolHandler.ts`: EC2-related tools
  - `s3ToolHandler.ts`: S3-related tools

## Prerequisites

- Node.js (v14+)
- npm or yarn
- AWS credentials configured (via environment variables or `~/.aws/credentials`)

## Setup

1. Install dependencies:
   ```bash
   npm install
   ```

2. Build the project:
   ```bash
   npm run build
   ```

3. Configure AWS credentials (if not already set up):
   ```bash
   # Option 1: Environment variables
   export AWS_ACCESS_KEY_ID=your_access_key
   export AWS_SECRET_ACCESS_KEY=your_secret_key
   export AWS_DEFAULT_REGION=us-east-1
   
   # Option 2: AWS CLI
   aws configure
   ```

## Running the Server

Start the server:

```bash
node build/index.js
```

The server runs on stdio (standard input/output) by default, allowing it to communicate with the agent through a direct pipe.

## Tool Specifications

### create_ec2_instance

Creates an AWS EC2 instance with specified parameters.

**Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| image_id | string | Yes | The ID of the AMI to use |
| min_count | integer | Yes | Minimum number of instances (usually 1) |
| max_count | integer | Yes | Maximum number of instances (usually 1) |
| instance_type | string | No | Instance type (default: "t2.micro") |
| key_name | string | No | SSH key pair name |
| security_group_ids | array | No | List of security group IDs |
| subnet_id | string | No | VPC subnet ID |
| tags | object | No | Key-value pairs for tagging (e.g., {"Name": "MyServer"}) |
| ... | ... | No | [Additional parameters as documented in the schema] |

**Example**:

```json
{
  "image_id": "ami-0c55b159cbfafe1f0",
  "min_count": 1,
  "max_count": 1,
  "instance_type": "t2.micro",
  "tags": {"Name": "WebServer", "Environment": "Dev"}
}
```

### create_s3_bucket

Creates an S3 bucket with the specified name and options.

**Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| bucket_name | string | Yes | Name of the bucket to create |
| region | string | No | AWS region (defaults to AWS_DEFAULT_REGION) |
| acl | string | No | Canned ACL (e.g., "private", "public-read") |

**Example**:

```json
{
  "bucket_name": "my-unique-bucket-name-2023",
  "region": "us-west-2",
  "acl": "private"
}
```

## Adding New Tools

To add a new AWS service tool:

1. Create a new handler file in `src/handlers/` (e.g., `rdsToolHandler.ts`)
2. Define input schema using JSON Schema format
3. Implement the handler function using AWS SDK
4. Register the tool in `src/toolRegistry.ts`
5. Rebuild the project

## Security Considerations

- This server executes AWS operations that can create, modify, or delete resources
- Ensure proper IAM permissions and use the principle of least privilege
- Consider implementing additional authentication for production use

## Troubleshooting

Common issues:

- **Authentication errors**: Ensure AWS credentials are properly configured
- **Permission errors**: Check IAM permissions for the operations you're attempting
- **Region-specific errors**: Some resources may not be available in all regions

## License

[Your license information here]
