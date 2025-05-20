import { ec2ToolDefinition } from './handlers/ec2ToolHandler.js';
import { s3ToolDefinition } from './handlers/s3ToolHandler.js';
export const toolDefinitions = [
    ec2ToolDefinition,
    s3ToolDefinition,
];
