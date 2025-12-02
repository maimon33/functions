#!/bin/bash

set -euo pipefail

# Check if instance ID is provided as argument
if [ $# -eq 0 ]; then
    echo "Usage: $0 <instance-id> [region]"
    echo "Example: $0 i-0266152c08f97b6f1 us-east-1"
    exit 1
fi

INSTANCE_ID="$1"
REGION="${2:-us-east-1}"  # Default to us-east-1 if not specified

echo "Starting root volume encryption process for instance: $INSTANCE_ID in region: $REGION"

# Validate AWS CLI is installed and configured
if ! command -v aws &> /dev/null; then
    echo "Error: AWS CLI is not installed"
    exit 1
fi

# Test AWS credentials
if ! aws sts get-caller-identity --region "$REGION" &> /dev/null; then
    echo "Error: AWS credentials not configured or invalid"
    exit 1
fi

# Get instance details
echo "Getting instance details..."
INSTANCE_INFO=$(aws ec2 describe-instances \
    --instance-ids "$INSTANCE_ID" \
    --region "$REGION" \
    --query 'Reservations[0].Instances[0]' \
    --output json)

if [ "$INSTANCE_INFO" == "null" ]; then
    echo "Error: Instance $INSTANCE_ID not found"
    exit 1
fi

# Extract root volume ID
ROOT_VOLUME_ID=$(echo "$INSTANCE_INFO" | jq -r '.BlockDeviceMappings[] | select(.DeviceName=="/dev/xvda" or .DeviceName=="/dev/sda1") | .Ebs.VolumeId')

if [ "$ROOT_VOLUME_ID" == "null" ] || [ -z "$ROOT_VOLUME_ID" ]; then
    echo "Error: Could not find root volume"
    exit 1
fi

echo "Root volume ID: $ROOT_VOLUME_ID"

# Check if volume is already encrypted
VOLUME_ENCRYPTED=$(aws ec2 describe-volumes \
    --volume-ids "$ROOT_VOLUME_ID" \
    --region "$REGION" \
    --query 'Volumes[0].Encrypted' \
    --output text)

if [ "$VOLUME_ENCRYPTED" == "True" ]; then
    echo "Root volume is already encrypted. No action needed."
    exit 0
fi

# Get current instance state
INSTANCE_STATE=$(echo "$INSTANCE_INFO" | jq -r '.State.Name')
echo "Current instance state: $INSTANCE_STATE"

# Stop instance if running
if [ "$INSTANCE_STATE" == "running" ]; then
    echo "Stopping instance..."
    aws ec2 stop-instances \
        --instance-ids "$INSTANCE_ID" \
        --region "$REGION" \
        --output text

    echo "Waiting for instance to stop..."
    aws ec2 wait instance-stopped \
        --instance-ids "$INSTANCE_ID" \
        --region "$REGION"

    echo "Instance stopped successfully"
fi

# Create snapshot of root volume
echo "Creating snapshot of root volume..."
SNAPSHOT_ID=$(aws ec2 create-snapshot \
    --volume-id "$ROOT_VOLUME_ID" \
    --description "Snapshot of $ROOT_VOLUME_ID for encryption" \
    --region "$REGION" \
    --query 'SnapshotId' \
    --output text)

echo "Snapshot ID: $SNAPSHOT_ID"

echo "Waiting for snapshot to complete..."
aws ec2 wait snapshot-completed \
    --snapshot-ids "$SNAPSHOT_ID" \
    --region "$REGION"

echo "Snapshot completed successfully"

# Get volume details for creating encrypted copy
VOLUME_INFO=$(aws ec2 describe-volumes \
    --volume-ids "$ROOT_VOLUME_ID" \
    --region "$REGION" \
    --query 'Volumes[0]' \
    --output json)

VOLUME_SIZE=$(echo "$VOLUME_INFO" | jq -r '.Size')
VOLUME_TYPE=$(echo "$VOLUME_INFO" | jq -r '.VolumeType')
AVAILABILITY_ZONE=$(echo "$VOLUME_INFO" | jq -r '.AvailabilityZone')

echo "Creating encrypted volume from snapshot..."
ENCRYPTED_VOLUME_ID=$(aws ec2 create-volume \
    --size "$VOLUME_SIZE" \
    --volume-type "$VOLUME_TYPE" \
    --snapshot-id "$SNAPSHOT_ID" \
    --availability-zone "$AVAILABILITY_ZONE" \
    --encrypted \
    --region "$REGION" \
    --query 'VolumeId' \
    --output text)

echo "Encrypted volume ID: $ENCRYPTED_VOLUME_ID"

echo "Waiting for encrypted volume to be available..."
aws ec2 wait volume-available \
    --volume-ids "$ENCRYPTED_VOLUME_ID" \
    --region "$REGION"

# Get root device name
ROOT_DEVICE=$(echo "$INSTANCE_INFO" | jq -r '.RootDeviceName')
echo "Root device name: $ROOT_DEVICE"

# Detach original root volume
echo "Detaching original root volume..."
aws ec2 detach-volume \
    --volume-id "$ROOT_VOLUME_ID" \
    --region "$REGION" \
    --output text

echo "Waiting for volume to detach..."
aws ec2 wait volume-available \
    --volume-ids "$ROOT_VOLUME_ID" \
    --region "$REGION"

# Attach encrypted volume as root
echo "Attaching encrypted volume as root..."
aws ec2 attach-volume \
    --volume-id "$ENCRYPTED_VOLUME_ID" \
    --instance-id "$INSTANCE_ID" \
    --device "$ROOT_DEVICE" \
    --region "$REGION" \
    --output text

echo "Waiting for encrypted volume to attach properly..."

# Wait for attachment to be fully stable with extended timeout (up to 1 hour)
MAX_WAIT_TIME=3600  # 1 hour in seconds
WAIT_INTERVAL=10    # Check every 10 seconds
ELAPSED_TIME=0

while [ $ELAPSED_TIME -lt $MAX_WAIT_TIME ]; do
    ATTACH_STATE=$(aws ec2 describe-volumes \
        --volume-ids "$ENCRYPTED_VOLUME_ID" \
        --region "$REGION" \
        --query 'Volumes[0].Attachments[0].State' \
        --output text 2>/dev/null || echo "not-attached")

    if [ "$ATTACH_STATE" == "attached" ]; then
        echo "Volume attachment verified as stable"
        # Additional 30-second stabilization period
        echo "Allowing 30 seconds for attachment to fully stabilize..."
        sleep 30
        break
    fi

    echo "Volume attachment state: $ATTACH_STATE - waiting... (${ELAPSED_TIME}s elapsed)"
    sleep $WAIT_INTERVAL
    ELAPSED_TIME=$((ELAPSED_TIME + WAIT_INTERVAL))
done

if [ $ELAPSED_TIME -ge $MAX_WAIT_TIME ]; then
    echo "ERROR: Volume attachment did not complete within 1 hour"
    echo "Current attachment state: $(aws ec2 describe-volumes --volume-ids "$ENCRYPTED_VOLUME_ID" --region "$REGION" --query 'Volumes[0].Attachments[0].State' --output text)"
    exit 1
fi

# Verify attachment one more time before starting instance
FINAL_ATTACH_STATE=$(aws ec2 describe-volumes \
    --volume-ids "$ENCRYPTED_VOLUME_ID" \
    --region "$REGION" \
    --query 'Volumes[0].Attachments[0].State' \
    --output text)

if [ "$FINAL_ATTACH_STATE" != "attached" ]; then
    echo "ERROR: Volume is not properly attached. State: $FINAL_ATTACH_STATE"
    exit 1
fi

# Start instance
echo "Volume is properly attached. Starting instance..."
aws ec2 start-instances \
    --instance-ids "$INSTANCE_ID" \
    --region "$REGION" \
    --output text

echo "Waiting for instance to start..."
aws ec2 wait instance-running \
    --instance-ids "$INSTANCE_ID" \
    --region "$REGION"

echo "Instance started successfully with encrypted root volume"

# Tag the old volume for cleanup
echo "Tagging old unencrypted volume for cleanup..."
aws ec2 create-tags \
    --resources "$ROOT_VOLUME_ID" \
    --tags Key=Name,Value="OLD-UNENCRYPTED-ROOT-$INSTANCE_ID" Key=Status,Value="ReadyForDeletion" \
    --region "$REGION"

echo ""
echo "=== ENCRYPTION PROCESS COMPLETED ==="
echo "Instance ID: $INSTANCE_ID"
echo "Old unencrypted volume: $ROOT_VOLUME_ID (tagged for cleanup)"
echo "New encrypted volume: $ENCRYPTED_VOLUME_ID"
echo "Snapshot ID: $SNAPSHOT_ID"
echo ""
echo "IMPORTANT: Verify the instance boots correctly before deleting the old volume!"
echo "To delete old volume after verification: aws ec2 delete-volume --volume-id $ROOT_VOLUME_ID --region $REGION"