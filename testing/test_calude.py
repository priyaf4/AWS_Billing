# pip install boto3

import boto3
import json
from botocore.exceptions import ClientError

# Configuration
AWS_REGION = "ap-southeast-2"  # Change to your AWS region (e.g., ap-south-1)
ACCESS_KEY = "YOUR_ACCESS_KEY_ID"      # Your IAM user Access Key
SECRET_KEY = "YOUR_SECRET_ACCESS_KEY"  # Your IAM user Secret Key

# Choose your Claude Model ID on Bedrock
# Example: Claude 3.5 Haiku or Claude 3.5 Sonnet
MODEL_ID = "anthropic.claude-3-5-haiku-20241022-v1:0"

def ask_claude(prompt_text):
    try:
        # Initialize the Bedrock Runtime client
        bedrock_runtime = boto3.client(
            'bedrock-runtime',
            region_name=AWS_REGION,
            aws_access_key_id=ACCESS_KEY,
            aws_secret_access_key=SECRET_KEY
        )

        # Format the request body according to Anthropic's Messages API standard on Bedrock
        payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 500,
            "messages": [
                {
                    "role": "user",
                    "content": prompt_text
                }
            ]
        }

        # Invoke the model
        response = bedrock_runtime.invoke_model(
            modelId=MODEL_ID,
            body=json.dumps(payload)
        )

        # Parse the response
        response_body = json.loads(response['body'].read())
        answer = response_body['content'][0]['text']
        
        print("--- Claude's Response ---")
        print(answer)
        return answer

    except ClientError as e:
        print(f"Error invoking Claude: {e}")
        return None

if __name__ == "__main__":
    ask_claude("Hello Claude! Confirm that you are running successfully on AWS Bedrock for my RAG project.")