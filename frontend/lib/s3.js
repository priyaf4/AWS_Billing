import { S3Client } from "@aws-sdk/client-s3";

export const UPLOAD_PREFIX = "uploads/";

let client;

// Credentials are read from AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY by the SDK.
export function getS3() {
  const region = process.env.AWS_REGION;
  const bucket = process.env.S3_BUCKET_NAME;
  if (!region || !bucket) {
    throw new Error("S3 is not configured. Set AWS_REGION and S3_BUCKET_NAME in .env.local");
  }
  client ??= new S3Client({ region });
  return { client, bucket };
}
