import re
import sys
import logging
from bugswarm.common import log
from bugswarm.common.credentials import GITHUB_TOKENS
from bugswarm.common.github_wrapper import GitHubWrapper


def parse_url(url):
    # https://github.com/<owner>/<repo-name>/actions/runs/<run_id>
    # https://github.com/<owner>/<repo-name>/actions/runs/<run_id>/jobs/<job_id>
    match = re.match(r'.*github.com/(\S+)/actions/runs/(\d+)(/jobs/(\d+))?', url)
    if match:
        return match.group(1), match.group(2), match.group(4)
    return None, None, None


def list_job_ids(repo, run_id, job_id):
    github_wrapper = GitHubWrapper(GITHUB_TOKENS)
    status, json_data = github_wrapper.get('https://api.github.com/repos/{}/actions/runs/{}/jobs'.format(repo, run_id))

    if status is None or not status.ok:
        log.error('Invalid GitHub Actions URL')
        return 1

    jobs = json_data['jobs']
    if job_id:
        # Search for Job ID
        html_url = 'https://github.com/{}/actions/runs/{}/jobs/{}'.format(repo, run_id, job_id)
        job = next(filter(lambda x: x['html_url'] == html_url, jobs), None)
        if job is None:
            log.error('Cannot find this job in GitHub API.')
            return 1
        jobs = [job]
    else:
        log.info('There are {} jobs in this workflow run.'.format(json_data['total_count']))

    for job in jobs:
        if not job_id:
            log.info('=========================')
        log.info('Job ID: {}'.format(job['id']))
        log.info('Job Name: {}'.format(job['name']))
        log.info('Job URL: {}'.format(job['html_url']))
    return 0


def main():
    log.config_logging(getattr(logging, 'INFO', None))
    if len(sys.argv) == 2:
        # Get Job IDs
        repo, run_id, job_id = parse_url(sys.argv[1])
        if repo is None:
            log.error('This is not a valid GitHub Actions URL.')
            return 1
        return list_job_ids(repo, run_id, job_id)
    else:
        log.error('Usage: python3 get_job_id.py <github_actions_url>')
        return 1


if __name__ == '__main__':
    sys.exit(main())
