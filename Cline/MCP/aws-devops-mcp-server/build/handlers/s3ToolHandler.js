import { S3Client, CreateBucketCommand } from '@aws-sdk/client-s3';
const s3Client = new S3Client({
    region: process.env.AWS_DEFAULT_REGION || 'us-east-1',
});
export async function createS3BucketHandler(args) {
    const params = {
        Bucket: args.bucket_name,
        ACL: args.acl,
        CreateBucketConfiguration: args.region
            ? { LocationConstraint: args.region }
            : undefined,
    };
    try {
        await s3Client.send(new CreateBucketCommand(params));
        return { success: true, message: `S3 bucket '${args.bucket_name}' created successfully.` };
    }
    catch (error) {
        return { success: false, message: `Error creating S3 bucket: ${error.message || String(error)}` };
    }
}
export function isValidCreateS3BucketArgs(args) {
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
