// Express HTTP wrapper for MCP server
import express from 'express';
import bodyParser from 'body-parser';
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { ListToolsRequestSchema, CallToolRequestSchema } from '@modelcontextprotocol/sdk/types.js';
import { toolDefinitions } from './toolRegistry.js';
// Import definitions for type casting
import { ec2ToolDefinition } from './handlers/ec2ToolHandler.js';
import { s3ToolDefinition } from './handlers/s3ToolHandler.js';

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


// Register ListTools dynamically from tool registry
mcpServer.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: toolDefinitions.map(({ name, description, inputSchema }) => ({ name, description, inputSchema })),
}));

// Express HTTP server
const app = express();
app.use(bodyParser.json());

app.post('/execute_tool/:tool_name', async (req, res) => {
  const toolName = req.params.tool_name;
  const currentToolDef = toolDefinitions.find((t) => t.name === toolName);
  if (!currentToolDef) {
    res.status(400).json({ status: 'error', error: `Unknown tool: ${toolName}` });
    return;
  }
  const args = req.body;
  let handlerResult; // To store the result from the handler

  try {
    // Use if/else if on currentToolDef.name and cast to specific type
    if (currentToolDef.name === 'create_ec2_instance') {
      const def = currentToolDef as typeof ec2ToolDefinition; // Cast
      if (def.isValidArgs(args)) { // args is now CreateEc2InstanceArgs
        handlerResult = await def.handler(args); // def.handler expects CreateEc2InstanceArgs
      } else {
        res.status(400).json({ status: 'error', error: `Invalid arguments for ${toolName}` });
        return;
      }
    } else if (currentToolDef.name === 'create_s3_bucket') {
      const def = currentToolDef as typeof s3ToolDefinition; // Cast
      if (def.isValidArgs(args)) { // args is now CreateS3BucketArgs
        handlerResult = await def.handler(args); // def.handler expects CreateS3BucketArgs
      } else {
        res.status(400).json({ status: 'error', error: `Invalid arguments for ${toolName}` });
        return;
      }
    } else {
      // This case should ideally not be reached if toolDefinitions are correctly managed
      // and toolName is validated against them.
      console.error(`Unknown tool name '${toolName}' encountered after finding definition.`);
      res.status(500).json({ status: 'error', error: 'Internal server error: unknown tool definition type after validation' });
      return;
    }

    if (handlerResult.success) {
      res.json({ status: 'success', result: handlerResult.message });
    } else {
      res.json({ status: 'error', error: handlerResult.message });
    }
  } catch (err: any) {
    console.error(`Error in '${toolName}' handler:`, err);
    res.status(500).json({ status: 'error', error: err.message || String(err) });
  }
});
// Tools discovery endpoint
app.get('/tools', (_req, res) => {
  res.json({
    tools: toolDefinitions.map(({ name, description, inputSchema }) => ({ name, description, inputSchema })),
  });
});

// Health check endpoint
app.get('/healthz', (_req, res) => res.send('OK'));

const PORT = process.env.PORT || 8000;
app.listen(PORT, () => {
  console.log(`MCP HTTP wrapper listening on port ${PORT}`);
});
