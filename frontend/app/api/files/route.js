import { NextResponse } from "next/server";
import { GetObjectCommand, ListObjectsV2Command, PutObjectCommand } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
import { getSessionUser } from "@/lib/session";
import { getS3, UPLOAD_PREFIX } from "@/lib/s3";

function unauthorized() {
  return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
}

function serverError(err) {
  console.error(err);
  return NextResponse.json({ error: err.message || "S3 request failed" }, { status: 500 });
}

// List uploaded files, each with a short-lived download link.
export async function GET(request) {
  if (!getSessionUser(request)) return unauthorized();

  try {
    const { client, bucket } = getS3();
    const files = [];
    let ContinuationToken;
    do {
      const page = await client.send(
        new ListObjectsV2Command({ Bucket: bucket, Prefix: UPLOAD_PREFIX, ContinuationToken })
      );
      for (const obj of page.Contents ?? []) {
        if (obj.Key === UPLOAD_PREFIX) continue;
        files.push({
          key: obj.Key,
          name: obj.Key.slice(UPLOAD_PREFIX.length).replace(/^\d+-/, ""),
          size: obj.Size,
          lastModified: obj.LastModified,
          url: await getSignedUrl(
            client,
            new GetObjectCommand({ Bucket: bucket, Key: obj.Key }),
            { expiresIn: 600 }
          ),
        });
      }
      ContinuationToken = page.NextContinuationToken;
    } while (ContinuationToken);

    files.sort((a, b) => new Date(b.lastModified) - new Date(a.lastModified));
    return NextResponse.json({ files });
  } catch (err) {
    return serverError(err);
  }
}

// Upload a single file sent as multipart form data under the "file" field.
export async function POST(request) {
  if (!getSessionUser(request)) return unauthorized();

  try {
    const form = await request.formData();
    const file = form.get("file");
    if (!file || typeof file === "string") {
      return NextResponse.json({ error: "No file provided" }, { status: 400 });
    }

    const { client, bucket } = getS3();
    const safeName = file.name.replace(/[^\w.\-]+/g, "_");
    const key = `${UPLOAD_PREFIX}${Date.now()}-${safeName}`;

    await client.send(
      new PutObjectCommand({
        Bucket: bucket,
        Key: key,
        Body: Buffer.from(await file.arrayBuffer()),
        ContentType: file.type || "application/octet-stream",
      })
    );
    return NextResponse.json({ ok: true, key });
  } catch (err) {
    return serverError(err);
  }
}
