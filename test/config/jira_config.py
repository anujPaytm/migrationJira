import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class JiraConfig:
    """JIRA configuration class"""
    
    def __init__(self):
        self.api_token = os.getenv('JIRA_API_TOKEN')
        self.project_key = os.getenv('JIRA_PROJECT_KEY')
        self.domain = os.getenv('JIRA_DOMAIN')
        self.email = os.getenv('JIRA_EMAIL')
        
        # Migration settings
        self.dry_run = os.getenv('DRY_RUN', 'true').lower() == 'true'
        self.batch_size = int(os.getenv('BATCH_SIZE', '10'))
        self.max_retries = int(os.getenv('MAX_RETRIES', '3'))
        self.retry_delay = int(os.getenv('RETRY_DELAY', '5'))
        
        # JIRA URL
        self.jira_url = f"https://{self.domain}"
        
    def validate(self):
        """Validate configuration"""
        required_fields = ['api_token', 'project_key', 'domain', 'email']
        missing_fields = [field for field in required_fields if not getattr(self, field)]
        
        if missing_fields:
            raise ValueError(f"Missing required configuration: {missing_fields}")
        
        return True
    
    def get_jira_options(self):
        """Get JIRA options for python-jira library"""
        return {
            'server': self.jira_url,
            'verify': True
        }
    
    def get_auth(self):
        """Get authentication tuple for requests"""
        return (self.email, self.api_token)
