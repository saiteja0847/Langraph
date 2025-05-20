import unittest
from unittest.mock import patch, MagicMock
import main

class TestDevOpsAgent(unittest.TestCase):
    @patch("main.ec2_client")
    def test_run_ec2_instance_success(self, mock_ec2_client):
        # Mock the response from boto3
        mock_ec2_client.run_instances.return_value = {
            "Instances": [{"InstanceId": "i-1234567890abcdef0"}]
        }
        result = main.run_ec2_instance()
        self.assertIn("EC2 instance launched successfully", result)
        self.assertIn("i-1234567890abcdef0", result)

    @patch("main.ec2_client")
    def test_run_ec2_instance_error(self, mock_ec2_client):
        # Simulate an exception
        mock_ec2_client.run_instances.side_effect = Exception("Test error")
        result = main.run_ec2_instance()
        self.assertIn("Error launching EC2 instance", result)
        self.assertIn("Test error", result)

    def test_parse_intent(self):
        self.assertEqual(main.parse_intent("Please run an EC2 instance"), "run_ec2_instance")
        self.assertEqual(main.parse_intent("Launch EC2 now"), "run_ec2_instance")
        self.assertEqual(main.parse_intent("Something else"), "unknown")

if __name__ == "__main__":
    unittest.main()
