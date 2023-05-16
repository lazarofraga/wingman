"""
Main module for the side-gryper
"""
import argparse

# Initialize parser
parser = argparse.ArgumentParser(
    description="Tool to perform a vulnerability scan on the filesystem of your cloud resources."
)

# Add arguments
parser.add_argument("cloud_service", type=str, help="Cloud service name")
parser.add_argument(
    "-i",
    "--instance_ids",
    type=str,
    default=None,
    help="Compute instance IDs (comma-separated)",
)
parser.add_argument(
    "-l",
    "--list_instances",
    action="store_true",
    help="List all instances for the specified cloud service",
)

# Parse arguments
args = parser.parse_args()

# Access arguments values
cloud_service = args.cloud_service
instance_ids = args.instance_ids.split(",") if args.instance_ids else None
list_instances = args.list_instances

# List of supported cloud services
supported_services = ["do"]

# Check if provided cloud service is supported
if cloud_service not in supported_services:
    raise ValueError(
        f'Unsupported cloud service. Supported services are: {", ".join(supported_services)}'
    )

# Your script logic goes here
if cloud_service == "do":
    import do

    if list_instances:
        print(f"Listing all instances for {cloud_service}.")
        do.list_instances()
    elif instance_ids:
        do.scan(instance_ids=instance_ids)
    else:
        do.scan()
