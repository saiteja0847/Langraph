#!/usr/bin/env node
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { CallToolRequestSchema, ErrorCode, ListToolsRequestSchema, McpError, } from '@modelcontextprotocol/sdk/types.js';
import { toolDefinitions } from './toolRegistry.js';
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
            tools: toolDefinitions.map(({ name, description, inputSchema }) => ({ name, description, inputSchema })),
        }));
        this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
            const toolName = request.params.name;
            const currentToolDef = toolDefinitions.find((t) => t.name === toolName);
            if (!currentToolDef) {
                throw new McpError(ErrorCode.MethodNotFound, `Unknown tool: ${toolName}`);
            }
            const toolArgs = request.params.arguments;
            let handlerResult; // To store { success: boolean, message: string }
            try {
                if (currentToolDef.name === 'create_ec2_instance') {
                    const def = currentToolDef;
                    if (def.isValidArgs(toolArgs)) {
                        handlerResult = await def.handler(toolArgs);
                    }
                    else {
                        throw new McpError(ErrorCode.InvalidParams, `Invalid arguments for ${toolName}`);
                    }
                }
                else if (currentToolDef.name === 'create_s3_bucket') {
                    const def = currentToolDef;
                    if (def.isValidArgs(toolArgs)) {
                        handlerResult = await def.handler(toolArgs);
                    }
                    else {
                        throw new McpError(ErrorCode.InvalidParams, `Invalid arguments for ${toolName}`);
                    }
                }
                else {
                    console.error(`Internal error: Unhandled tool name '${toolName}' in CallToolRequestSchema handler.`);
                    throw new McpError(ErrorCode.MethodNotFound, `Internal error: Unhandled tool: ${toolName}`);
                }
                return {
                    content: [{ type: 'text', text: handlerResult.message }],
                    isError: !handlerResult.success,
                };
            }
            catch (err) {
                if (err instanceof McpError) {
                    throw err; // Re-throw McpError if it's already one
                }
                console.error(`Error in '${toolName}' tool handler:`, err);
                // For other errors, wrap them in a standard response
                return {
                    content: [{ type: 'text', text: `Internal server error: ${err.message || String(err)}` }],
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
