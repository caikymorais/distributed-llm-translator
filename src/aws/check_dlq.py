import json

import boto3

from src.config import AWS_REGION, SQS_DLQ_URL


def main():
    if not SQS_DLQ_URL:
        raise RuntimeError("SQS_DLQ_URL não configurado")

    sqs = boto3.client("sqs", region_name=AWS_REGION)
    attrs = sqs.get_queue_attributes(
        QueueUrl=SQS_DLQ_URL,
        AttributeNames=[
            "ApproximateNumberOfMessages",
            "ApproximateNumberOfMessagesNotVisible",
        ],
    )["Attributes"]

    print(json.dumps({
        "dlq_url": SQS_DLQ_URL,
        "messages_available": attrs.get("ApproximateNumberOfMessages"),
        "messages_in_flight": attrs.get("ApproximateNumberOfMessagesNotVisible"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
