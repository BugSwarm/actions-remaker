import sys
import logging
from dataclasses import dataclass
from bugswarm.common import log
from bugswarm.common.json import write_json
from bugswarm.common.credentials import GITHUB_TOKENS
from bugswarm.common.github_wrapper import GitHubWrapper
from bugswarm.utils import is_archive, is_resettable
from bugswarm.construct_job_config import process

INPUT_FILE_PATH = 'reproducer/task.json'


@dataclass
class JobData:
    job_id: int
    branch: str
    build_id: int
    head_sha: str
    github_archived: bool
    resettable: bool
    job_config: dict
    kind: str
    command: str
    conclusion: str


def get_build_data(repo, build_id, github_wrapper):
    # Given repo and build_id, return all information related to the build
    # API: https://api.github.com/repos/<repo>/actions/runs/<job_id>
    status, json_data = github_wrapper.get('https://api.github.com/repos/{}/actions/runs/{}'.format(repo, build_id))
    if status is None or not status.ok:
        log.error('Invalid repo slug or build_id')
        exit(1)

    branch = json_data['head_branch']
    head_sha = json_data['head_sha']
    github_archived = is_archive(repo, head_sha)
    resettable = is_resettable(repo, head_sha)
    workflow_path = json_data['path']

    return branch, head_sha, github_archived, resettable, workflow_path


def get_job_data(repo, job_id, github_wrapper):
    # Given repo and job_id, return all information related to the job
    # API: https://api.github.com/repos/<repo>/actions/jobs/<job_id>
    status, json_data = github_wrapper.get('https://api.github.com/repos/{}/actions/jobs/{}'.format(repo, job_id))
    if status is None or not status.ok:
        log.error('Invalid repo slug or job_id.')
        exit(1)

    build_id = json_data['run_id']
    conclusion = json_data['conclusion']
    job_name = json_data['name']

    if conclusion not in {'failure', 'success'}:
        log.error('Unsupported job, final job status should be failure or success.')
        exit(1)

    failed_step_number = None
    for s, step in enumerate(json_data['steps']):
        if step['conclusion'] == 'failure':
            failed_step_number = s
            break

    branch, head_sha, github_archived, resettable, workflow_path = get_build_data(repo, build_id, github_wrapper)
    job_config, kind, command = process(repo, workflow_path, build_id, head_sha, job_name, failed_step_number)

    return JobData(job_id, branch, build_id, head_sha, github_archived, resettable, job_config, kind, command,
                   conclusion)


def update_input_json(output, job):
    key = 'passed' if job.conclusion == 'success' else 'failed'
    output['jobpairs'][0][key + '_job']['job_id'] = job.job_id
    output['jobpairs'][0]['failed_step_command'] = job.command
    output['jobpairs'][0]['failed_step_kind'] = job.kind
    output[key + '_build'] = {
        'build_id': job.build_id,
        'travis_merge_sha': None,
        'base_sha': '',
        'head_sha': job.head_sha,
        'github_archived': job.github_archived,
        'resettable': job.resettable,
        'committed_at': '',
        'message': '',
        'jobs': [{'build_job': '0.0',
                  'job_id': job.job_id,
                  'config': job.job_config or {},
                  'language': 'java'}],
        'has_submodules': False
    }


def generate_input_file(repo, first_job_id, second_job_id=None):
    """Given repo and job_id, generate the input file for entry.py"""
    github_wrapper = GitHubWrapper(GITHUB_TOKENS)
    first_job = get_job_data(repo, first_job_id, github_wrapper)

    output = {
        'repo': repo,
        'ci_service': 'github',
        'repo_mined_version': '',
        'pr_num': -1,
        'merged_at': '',
        'branch': first_job.branch,
        'base_branch': '',
        'is_error_pass': False,
        'failed_build': {
            'build_id': 0,
            'travis_merge_sha': None,
            'base_sha': '',
            'head_sha': '',
            'github_archived': False,
            'resettable': False,
            'committed_at': '',
            'message': '',
            'jobs': [{'build_job': '0.0',
                      'job_id': 0,
                      'config': {},
                      'language': 'java'}],
            'has_submodules': False
        },
        'passed_build': {
            'build_id': 0,
            'travis_merge_sha': None,
            'base_sha': '',
            'head_sha': '',
            'github_archived': False,
            'resettable': False,
            'committed_at': '',
            'message': '',
            'jobs': [{'build_job': '1.0',
                      'job_id': 0,
                      'config': {},
                      'language': 'java'}],
            'has_submodules': False
        },
        'jobpairs': [
            {
                "build_system": "NA",
                "failed_job": {
                    "heuristically_parsed_image_tag": None,
                    "job_id": 0
                },
                "failed_step_command": None,
                "failed_step_kind": None,
                "filtered_reason": None,
                "is_filtered": False,
                "metrics": {
                    "additions": 0,
                    "changes": 0,
                    "deletions": 0,
                    "num_of_changed_files": 0
                },
                "passed_job": {
                    "heuristically_parsed_image_tag": None,
                    "job_id": 0
                }
            },
        ],
    }

    update_input_json(output, first_job)
    if second_job_id:
        second_job = get_job_data(repo, second_job_id, github_wrapper)
        if first_job.conclusion == second_job.conclusion:
            log.error('Please enter one failed job and one passed job. Not {} & {}'.format(
                first_job.conclusion, second_job.conclusion
            ))
            exit(1)

        if first_job.branch != second_job.branch:
            log.error('Please enter one failed job and one passed job from the same branch. Not {} & {}'.format(
                first_job.branch, second_job.branch
            ))
            exit(1)

        update_input_json(output, second_job)

    return output


def main():
    log.config_logging(getattr(logging, 'INFO', None))
    if 3 <= len(sys.argv) <= 4:
        # Generate input json file.
        json_file = generate_input_file(sys.argv[1], sys.argv[2], None if len(sys.argv) == 3 else sys.argv[3])
        write_json(INPUT_FILE_PATH, [json_file])
        log.info('Added input file to {}'.format(INPUT_FILE_PATH))
    else:
        log.error('Usage: python3 entry.py <repo> (<failed_job_id> <passed_job_id> | <job_id>)')
        return 1


if __name__ == '__main__':
    sys.exit(main())
