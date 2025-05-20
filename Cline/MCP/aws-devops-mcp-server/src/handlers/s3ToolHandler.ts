import { S3Client, CreateBucketCommand, CreateBucketCommandInput, BucketCannedACL, BucketLocationConstraint } from '@aws-sdk/client-s3';

const s3Client = new S3Client({
  region: process.env.AWS_DEFAULT_REGION || 'us-east-1',
});

export interface CreateS3BucketArgs {
  bucket_name: string;
  region?: string;
  acl?: string;
}

export async function createS3BucketHandler(args: CreateS3BucketArgs) {
  const params: CreateBucketCommandInput = {
    Bucket: args.bucket_name,
    ACL: args.acl as BucketCannedACL | undefined,
    CreateBucketConfiguration: args.region
      ? { LocationConstraint: args.region as BucketLocationConstraint }
      : undefined,
  };
  try {
    await s3Client.send(new CreateBucketCommand(params));
    return { success: true, message: `S3 bucket '${args.bucket_name}' created successfully.` };
  } catch (error: any) {
    return { success: false, message: `Error creating S3 bucket: ${error.message || String(error)}` };
  }
}

export function isValidCreateS3BucketArgs(args: any): args is CreateS3BucketArgs {
  return typeof args === 'object' && args !== null && typeof args.bucket_name === 'string';
}

export const s3ToolDefinition = {
  name: 'create_s3_bucket',
  description: 'Creates an AWS S3 bucket with the specified name. Optionally specify region and ACL.',
  inputSchema: {
    type: 'object',
    properties: {
      bucket_name: { type: 'string', description: 'The name of the bucket to create.' },
      region: { type: 'string', description: 'AWS region to create the bucket in, defaults to AWS_DEFAULT_REGION.' },
      acl: { type: 'string', description: 'Canned ACL to apply to bucket (e.g., public-read, private).' },
    },
    required: ['bucket_name'],
  },
  handler: createS3BucketHandler,
  isValidArgs: isValidCreateS3BucketArgs,
};
