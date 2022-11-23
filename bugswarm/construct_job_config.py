import re
from copy import deepcopy
from itertools import product

import cachecontrol
import requests
import yaml

from bugswarm.common import log
from bugswarm.common.credentials import GITHUB_TOKENS

# Matches ${{ matrix.(name) }}, where (name) is anything that isn't a space or '}'.
# match.group(1) is the name of the matrix variable.
MATRIX_INTERPOLATE_REGEX = re.compile(r'\${{\s*matrix\.([^\s}]+)\s*}}')


class RecoverableException(Exception):
    pass


def get_job_api_name(base_name: str, matrix_combination, default_keys):
    """
    Finds the job's API name by interpolating the appropriate matrix variables.
    """

    # If a job's name has no interpolated variables, it defaults to the name
    # followed by a comma-separated list of the default matrix values.
    interpolations = []
    for key in default_keys:
        if key in matrix_combination and matrix_combination[key] != '':
            interpolations.append('${{{{ matrix.{} }}}}'.format(key))

    intermediate_name = base_name
    if interpolations and not re.search(MATRIX_INTERPOLATE_REGEX, intermediate_name):
        intermediate_name = '{} ({})'.format(base_name, ', '.join(interpolations))

    # Find the start/end indexes of all interpolated matrix variables.
    indexes = []
    for match in re.finditer(MATRIX_INTERPOLATE_REGEX, intermediate_name):
        key = match.group(1)
        value = str(matrix_combination[key]) if key in matrix_combination else ''
        indexes.append((match.start(), match.end(), value))

    # Interpolate
    job_name = intermediate_name
    for start, end, value in reversed(indexes):
        job_name = job_name[:start] + value + job_name[end:]

    return job_name.strip()


def partial_match(d1, d2):
    for key, val in d1.items():
        if key in d2 and d2[key] != val:
            return False
    return True


def build_combinations(job_matrix):
    """
    Given a GHA job matrix, generate all possible permutations of that
    matrix, taking into account include and exclude rules.
    """

    # Separate matrix includes and excludes
    job_matrix = deepcopy(job_matrix)
    includes = excludes = []
    if 'include' in job_matrix:
        includes = job_matrix['include']
        del job_matrix['include']
    if 'exclude' in job_matrix:
        excludes = job_matrix['exclude']
        del job_matrix['exclude']

    if len(job_matrix) == 0:
        combinations = []
    else:
        # Separate matrix keys and values into their own lists
        keys, values = zip(*job_matrix.items())
        # For each combination of values, generate {key1: value1, key2: value2, ...}
        combinations = [dict(zip(keys, prod)) for prod in product(*values)]

    # Indicates whether an include needs to be appended to the end of combinations
    includes_used = [False for _ in includes]

    # Handle excludes first
    i = 0
    while i < len(combinations):
        matrix = combinations[i]
        for exclude in excludes:
            if partial_match(exclude, matrix):
                del combinations[i]
                break
        else:
            i += 1

    # Handle includes with partial matches
    for i, matrix in enumerate(combinations):
        updated_matrix = deepcopy(matrix)
        for j, include in enumerate(includes):
            if partial_match(include, matrix):
                updated_matrix.update(include)
                includes_used[j] = True
        combinations[i] = updated_matrix

    # Handle includes with no match (just append to end)
    for i, used in enumerate(includes_used):
        if not used:
            combinations.append(includes[i])

    return combinations


def expand_job_matrixes(workflow: dict):
    """
    For each job in a workflow file, expands that job into all possible
    combinations of its matrix parameters. Returns each list of
    combinations in descending order of length.

    For example, if the input is this:
    ```
    {
        job1: {strategy: {matrix: {foo: [1, 2], bar: [3, 4]}}, ...},
        job2: {strategy: {matrix: {baz: [5, 6]}}, ...}
    }
    ```

    then the output will be this:
    ```
    [
        [
            ("job1 (1, 3)", "job1", {strategy: {matrix: {foo: 1, bar: 3}}, ...}),
            ("job1 (1, 4)", "job1", {strategy: {matrix: {foo: 1, bar: 4}}, ...}),
            ("job1 (2, 3)", "job1", {strategy: {matrix: {foo: 2, bar: 3}}, ...}),
            ("job1 (2, 4)", "job1", {strategy: {matrix: {foo: 2, bar: 4}}, ...})
        ],
        [
            ("job2 (5)", "job2", {strategy: {matrix: {baz: 5}}, ...}),
            ("job2 (6)", "job2", {strategy: {matrix: {baz: 6}}, ...})
        ]
    ]
    ```
    """

    # List of lists of (<job's API name>, <job's workflow name>, <collapsed config>) tuples.
    # Tuples are grouped by job.
    names_and_configs: 'list[list[tuple[str, str, dict]]]' = []

    # Used to detect duplicates
    disambiguated = []

    for job_workflow_name, job in workflow.items():
        job_base_api_name = job['name'] if 'name' in job else job_workflow_name

        if 'strategy' in job and 'matrix' in job['strategy']:
            job_matrix = job['strategy']['matrix']

            # If a job.strategy.matrix is a string, it probably depends on the output of another job
            # (e.g. https://github.com/TechEmpower/FrameworkBenchmarks/actions/runs/2053331030/workflow).
            # Skip expanding those jobs, since we can't know what the matrix is without running it ourselves.
            if isinstance(job_matrix, str):
                log.warning("Job matrix probably depends on another job's output. Skipping.")
                continue

            # Detect duplicates that we can't disambiguate
            if (job_base_api_name, job_matrix) in disambiguated:
                raise RecoverableException()
            disambiguated.append((job_base_api_name, job_matrix))

            # All keys not added by include rules. Used to generate job_api_name.
            default_keys = [key for key in job_matrix if key not in ['include', 'exclude']]

            # For each possible combination of matrix values, generate the corresponding API name.
            # (Note: reliant on the specific order itertools.product generates. In practice it works fine.)
            names_and_configs.append([])
            for combination in build_combinations(job_matrix):
                config = deepcopy(job)
                config['strategy']['matrix'] = combination
                job_api_name = get_job_api_name(job_base_api_name, combination, default_keys)

                names_and_configs[-1].append((job_api_name, job_base_api_name, config))
        else:
            # Detect duplicates that we can't disambiguate
            if job_base_api_name in disambiguated:
                raise RecoverableException()
            disambiguated.append(job_base_api_name)

            names_and_configs.append([(job_base_api_name, job_base_api_name, job)])

    # Sort by length in descending order.
    return sorted(names_and_configs, key=lambda l: len(l), reverse=True)


def get_failed_step(failed_step_index: int, job_config: dict):
    steps = job_config['steps']

    # The first step in the API is always "Set up job", which has no equivalent in the workflow file.
    # So, decrement the target index by 1.
    index = failed_step_index - 1

    # If a job runs in a container, one of the first API steps is always "Initialize containers".
    # No workflow file equivalent, so decrement.
    if 'container' in job_config:
        index -= 1

    # For each unique docker image used by a `uses` step, an API step is added to the start called "Pull <image>".
    # No workflow file equivalent, so decrement.
    dockerhub_steps = set((step['uses'] for step in job_config['steps']
                           if 'uses' in step and step['uses'].startswith('docker://')))
    index -= len(dockerhub_steps)

    failed_step = steps[index]
    if 'uses' in failed_step:
        return 'uses', failed_step['uses']
    elif 'run' in failed_step:
        return 'run', failed_step['run']
    raise RecoverableException('Invalid workflow file: step has neither "uses" key nor "run" key')


def find_sequence(needle, haystack):
    # Inefficient, but we're not dealing with huge lists.
    for i in range(len(haystack)):
        if haystack[i:i + len(needle)] == needle:
            return i, i + len(needle)
    return None, None


def process(repo, workflow_path, build_id, commit, job_name, failed_step_number):
    # GitHubWrapper doesn't allow requests from raw.githubusercontent.com, and
    # anyway that site doesn't return json. Therefore, we use our own session.
    session = cachecontrol.CacheControl(requests.Session())

    # Assumes the first token will work (NOT GUARANTEED!)
    session.headers['Authorization'] = 'token {}'.format(GITHUB_TOKENS[0])

    # Parse workflow YML for each build pair in a group.
    workflow = get_workflow_object(session, repo, workflow_path, commit)

    try:
        # Expand each job in a workflow YML
        job_sequences = expand_job_matrixes(workflow)
    except RecoverableException:
        log.error('2 jobs with same name and matrix found. Cannot disambiguate.')
        return None, None, None

    # Match the expanded YML jobs with the API jobs by looking for sequences
    # where the names match.
    target_job_name = job_name.strip()

    for job_sequence in job_sequences:
        for potential_job in job_sequence:
            if potential_job[0] == target_job_name:
                job_config = potential_job[2]
                failed_step_kind = None
                failed_step_command = None

                if failed_step_number is not None:
                    try:
                        kind, command = get_failed_step(failed_step_number, job_config)
                    except RecoverableException as e:
                        log.warning(e)
                        continue
                    failed_step_kind = kind
                    failed_step_command = command
                return job_config, failed_step_kind, failed_step_command
    log.error('Unable to find job config')
    return None, None, None


def get_workflow_object(session, repo, workflow_path, commit):
    try:
        workflow_text = get_file_from_github(session, repo, commit, workflow_path)
        workflow_object = yaml.safe_load(workflow_text)
        return workflow_object['jobs']
    except requests.HTTPError:
        log.error('Unable to get workflow object due to HTTPError')
        exit(1)


def get_file_from_github(session, repo, commit, path):
    url = 'https://raw.githubusercontent.com/{}/{}/{}'.format(repo, commit, path)
    response = session.get(url)
    response.raise_for_status()
    return response.text
