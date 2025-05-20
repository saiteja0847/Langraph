import boto3
import os
from typing import List, Optional, Dict # Optional and Dict might be needed for Pydantic model
from langchain_core.tools import tool
from pydantic import BaseModel, Field # Import Pydantic components
from dotenv import load_dotenv

# Load environment variables to ensure boto3 can be configured if needed here
# although agent.py also does this. Best practice for standalone tool modules.
load_dotenv()

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

# Initialize boto3 EC2 client specifically for this tool module
# This makes the tool module more self-contained.
ec2_client = boto3.client(
    "ec2",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_DEFAULT_REGION,
)

# Define the EC2 creation function (actual Boto3 logic)
def create_ec2_instance(
    image_id: str,
    min_count: int,
    max_count: int,
    instance_type: str = "t2.micro",
    key_name: str = None,
    security_group_ids: List[str] = None,
    subnet_id: str = None,
    user_data: str = None,
    ebs_optimized: bool = False,
    monitoring_enabled: bool = False,
    availability_zone: str = None,
    tags: dict = None,
    disable_api_termination: bool = False,
    instance_initiated_shutdown_behavior: str = "stop",
    block_device_mappings: List[dict] = None,
    iam_instance_profile: dict = None,
    network_interfaces: List[dict] = None,
    placement: dict = None,
    credit_specification: dict = None,
    cpu_options: dict = None,
    metadata_options: dict = None,
    private_ip_address: str = None,
    client_token: str = None,
    launch_template: dict = None,
    instance_market_options: Optional[Dict] = None # Made dict optional
) -> str:
    """Internal function to create EC2 instance. Called by the decorated tool."""
    try:
        params = {
            "ImageId": image_id,
            "MinCount": min_count,
            "MaxCount": max_count,
            "InstanceType": instance_type,
        }
        if key_name: params["KeyName"] = key_name
        if security_group_ids: params["SecurityGroupIds"] = security_group_ids
        if subnet_id: params["SubnetId"] = subnet_id
        if user_data: params["UserData"] = user_data
        if ebs_optimized is not None: params["EbsOptimized"] = ebs_optimized
        if monitoring_enabled is not None: params["Monitoring"] = {"Enabled": monitoring_enabled}
        
        current_placement = params.get("Placement", {})
        if availability_zone: current_placement["AvailabilityZone"] = availability_zone
        if placement: current_placement.update(placement) # placement from args is a dict
        if current_placement: params["Placement"] = current_placement

        if tags: # tags from args is a dict
            params["TagSpecifications"] = [{
                "ResourceType": "instance",
                "Tags": [{"Key": k, "Value": v} for k, v in tags.items()]
            }]
        if disable_api_termination is not None: params["DisableApiTermination"] = disable_api_termination
        if instance_initiated_shutdown_behavior: params["InstanceInitiatedShutdownBehavior"] = instance_initiated_shutdown_behavior
        if block_device_mappings: params["BlockDeviceMappings"] = block_device_mappings # from args is List[dict]
        if iam_instance_profile: params["IamInstanceProfile"] = iam_instance_profile # from args is dict
        if network_interfaces: params["NetworkInterfaces"] = network_interfaces # from args is List[dict]
        if credit_specification: params["CreditSpecification"] = credit_specification # from args is dict
        if cpu_options: params["CpuOptions"] = cpu_options # from args is dict
        if metadata_options: params["MetadataOptions"] = metadata_options # from args is dict
        if private_ip_address: params["PrivateIpAddress"] = private_ip_address
        if client_token: params["ClientToken"] = client_token
        if launch_template: params["LaunchTemplate"] = launch_template # from args is dict
        if instance_market_options: params["InstanceMarketOptions"] = instance_market_options # from args is dict
        
        response = ec2_client.run_instances(**params)
        instance_ids = [inst["InstanceId"] for inst in response["Instances"]]
        return f"EC2 instance(s) launched successfully. Instance IDs: {instance_ids}"
    except Exception as e:
        return f"Error launching EC2 instance: {str(e)}"

# Pydantic model for create_ec2_instance_tool arguments
class CreateEc2InstanceArgs(BaseModel):
    image_id: str = Field(..., description="The ID of the AMI (Amazon Machine Image) to use for the instance. This is a required parameter.")
    min_count: int = Field(..., description="The minimum number of instances to launch. Usually 1. This is a required parameter.")
    max_count: int = Field(..., description="The maximum number of instances to launch. Usually 1. This is a required parameter.")
    instance_type: str = Field(default="t2.micro", description="The type of instance to launch, e.g., 't2.micro', 'm5.large'.")
    key_name: Optional[str] = Field(default=None, description="The name of the key pair for SSH access.")
    security_group_ids: Optional[List[str]] = Field(default=None, description="A list of security group IDs.")
    subnet_id: Optional[str] = Field(default=None, description="The ID of the subnet to launch the instance into.")
    user_data: Optional[str] = Field(default=None, description="User data to make available to the instance.")
    ebs_optimized: Optional[bool] = Field(default=False, description="Whether the instance is optimized for Amazon EBS I/O.")
    monitoring_enabled: Optional[bool] = Field(default=False, description="Enables detailed monitoring for the instance.")
    availability_zone: Optional[str] = Field(default=None, description="The Availability Zone to launch the instance into, e.g., 'us-east-1a'.")
    tags: Optional[Dict[str, str]] = Field(default=None, description="A dictionary of key-value pairs to assign as tags. For instance name, use key 'Name'. Example: {'Name': 'MyServer', 'Environment': 'Dev'}")
    disable_api_termination: Optional[bool] = Field(default=False, description="If true, enables instance termination protection.")
    instance_initiated_shutdown_behavior: Optional[str] = Field(default="stop", description="Whether the instance should 'stop' or 'terminate' when shut down from within the OS.")
    # Add other complex types as needed, using Optional[List[Dict]] or Optional[Dict]
    block_device_mappings: Optional[List[Dict]] = Field(default=None, description="Define EBS volumes. List of mappings, e.g., [{'DeviceName': '/dev/sda1', 'Ebs': {'VolumeSize': 30, 'VolumeType': 'gp3'}}]")
    iam_instance_profile: Optional[Dict[str, str]] = Field(default=None, description="IAM instance profile. Provide as {'Arn': 'arn:aws:iam::ACCOUNT:instance-profile/PROFILE_NAME'} or {'Name': 'PROFILE_NAME'}.")
    # For brevity, not all complex fields from the original schema are fully detailed here but can be added.
    # network_interfaces, placement, credit_specification, cpu_options, metadata_options, 
    # private_ip_address, client_token, launch_template, instance_market_options
    # The following fields are not yet in CreateEc2InstanceArgs but are in create_ec2_instance,
    # they can be added to CreateEc2InstanceArgs if needed by the LLM.
    # For now, they won't be passed by the LLM if not in CreateEc2InstanceArgs.
    # network_interfaces, placement, credit_specification, cpu_options, metadata_options, 
    # private_ip_address, client_token, launch_template, instance_market_options

@tool(args_schema=CreateEc2InstanceArgs)
def create_ec2_instance_tool(
    image_id: str,
    min_count: int,
    max_count: int,
    instance_type: str, # Default is handled by Pydantic model if not provided by LLM
    key_name: Optional[str] = None,
    security_group_ids: Optional[List[str]] = None,
    subnet_id: Optional[str] = None,
    user_data: Optional[str] = None,
    ebs_optimized: Optional[bool] = None, 
    monitoring_enabled: Optional[bool] = None, 
    availability_zone: Optional[str] = None,
    tags: Optional[Dict[str, str]] = None,
    disable_api_termination: Optional[bool] = None, 
    instance_initiated_shutdown_behavior: Optional[str] = None, 
    block_device_mappings: Optional[List[Dict]] = None,
    iam_instance_profile: Optional[Dict[str, str]] = None
    # Other complex parameters from CreateEc2InstanceArgs can be added here if they are defined in the model
) -> str:
    """Creates an AWS EC2 instance based on the provided parameters. This tool is used to provision virtual servers in AWS cloud.
    If the user specifies an 'instance name', 'server name', or 'name for the instance', interpret this as a request to set a tag with the key 'Name' and the value as the specified name. For example, if the user says 'name it MyWebApp', you should ensure this is part of the 'tags' argument as `tags={'Name': 'MyWebApp'}`. If other tags are also specified, merge this Name tag with them.
    Always ensure 'image_id', 'min_count', and 'max_count' are provided or inferred before calling."""
    
    # Values received here are already validated by Pydantic against CreateEc2InstanceArgs.
    # Defaults from Pydantic model are applied by Pydantic before this function is called if LLM didn't provide them.
    # We can directly pass these to the underlying function.
    return create_ec2_instance(
        image_id=image_id,
        min_count=min_count,
        max_count=max_count,
        instance_type=instance_type, 
        key_name=key_name,
        security_group_ids=security_group_ids,
        subnet_id=subnet_id,
        user_data=user_data,
        ebs_optimized=ebs_optimized, 
        monitoring_enabled=monitoring_enabled, 
        availability_zone=availability_zone,
        tags=tags,
        disable_api_termination=disable_api_termination, 
        instance_initiated_shutdown_behavior=instance_initiated_shutdown_behavior, 
        block_device_mappings=block_device_mappings,
        iam_instance_profile=iam_instance_profile
        # Note: The internal create_ec2_instance function has more parameters than listed here.
        # If those are added to CreateEc2InstanceArgs and this function's signature, they will be passed.
        # Otherwise, create_ec2_instance will use its own defaults for those not explicitly passed.
    )
