import sys

# GitHub
# A GitHub Access Token to perform Git Operations over HTTPS via the Git API.
# These GitHub tokens are hard-coded and can be used for token switching to
# minimize the time spent waiting for our GitHub quota to reset.
# Example: 
# GITHUB_TOKENS = ['my_personal_token']
GITHUB_TOKENS = []


# Please ignore the following variables.
DOCKER_HUB_REPO = '#'
DOCKER_HUB_USERNAME = '#'
DOCKER_HUB_PASSWORD = '#'
DOCKER_REGISTRY_REPO = '#'
DOCKER_REGISTRY_USERNAME = '#'
DOCKER_REGISTRY_PASSWORD = '#'


# GitHub check
if not GITHUB_TOKENS:
    print('[ERROR]: GITHUB_TOKENS has not been set. Please input your credentials under bugswarm/common/credentials.py')
    sys.exit(1)
