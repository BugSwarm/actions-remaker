import requests
import os

from git import GitDB, Repo
from bugswarm.common import log
from bugswarm.common.credentials import GITHUB_TOKENS


def is_archive(repo, commit):
    session = requests.session()
    session.headers = {'Authorization': 'token {}'.format(GITHUB_TOKENS[0])}
    response = session.head('https://github.com/{}/commit/{}'.format(repo, commit))

    return response.status_code != 404


def is_resettable(repo, commit):
    repo_path = os.path.abspath('./intermediates/tmp/{}'.format(repo.replace('/', '-')))

    # Clone repo
    if os.path.isdir(repo_path):
        log.info('Clone of repo {} already exists.'.format(repo))

        # Explicitly set odbt, or else Repo.iter_commits fails with a broken pipe. (I don't know why.)
        # (Possibly related: https://github.com/gitpython-developers/GitPython/issues/427)
        repo_obj = Repo(repo_path, odbt=GitDB)
    else:
        log.info('Cloning repo {}'.format(repo))
        repo_obj = Repo.clone_from('https://github.com/{}'.format(repo), repo_path, odbt=GitDB)

    # Fetch refs for all pulls and PRs
    log.info('Checking if a build is resettable...')
    repo_obj.remote('origin').fetch('refs/pull/*/head:refs/remotes/origin/pr/*')

    # Get all shas
    shas = [commit.hexsha for commit in repo_obj.iter_commits(branches='', remotes='')]
    return commit in shas
