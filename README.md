# ActionsRemaker
**A tool to reproduce workflow runs on GitHub Actions**

![ActionsRemaker](./figures/actions-remaker.png)

## Setting up

### Requirements

* Ubuntu 18.04 or higher
* Python 3.8
* Python3-virtualenv
* [Docker](https://docs.docker.com/engine/install/ubuntu/)
* [GitHub personal access token (classic) with repo scope](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token)

### Installation

1. Clone the repository
    ```shell
    ~$ git clone https://github.com/BugSwarm/actions-remaker
    ~$ cd actions-remaker
    ```

2. Create and activate a Python virtual environment
    ```shell
    ~/actions-remaker$ virtualenv -p python3.8 venv
    ~/actions-remaker$ . venv/bin/activate
    ```

3. Add personal access token to credentials
   - Open `bugswarm/common/credentials.py`
   - Replace `GITHUB_TOKENS = []` with `GITHUB_TOKENS = ['my_personal_token']`


4. Install dependencies
    ```shell
    (venv) ~/actions-remaker$ pip install -e .
    ```

## Usage

### Commands

- Get job ID from GitHub's website
    ```shell
    get_id.sh <github-url>
    ```
- Reproduce a single run with job ID
    ```shell
    run.sh -r <repo-slug> -j <job-id>
    ```
- Reproduce a fail-pass pair
    ```shell
    run.sh -r <repo-slug> -f <failed-job-id> -p <passed-job-id>
    ```


### Examples

1. Reproduce a [failed job](https://github.com/Grasscutters/Grasscutter/actions/runs/3344953329/jobs/5552953144) [(original log)](reproducer/intermediates/orig_logs/9179386809-orig.log) and a [passed job](https://github.com/Grasscutters/Grasscutter/actions/runs/3351485580/jobs/5552966102) [(original log)](reproducer/intermediates/orig_logs/9179402125-orig.log).

    Get failed job ID and passed job ID:
    ``` shell
    (venv) ~/actions-remaker$ bash get_id.sh https://github.com/Grasscutters/Grasscutter/actions/runs/3344953329
    ```
    ``` shell
    (venv) ~/actions-remaker$ bash get_id.sh https://github.com/Grasscutters/Grasscutter/actions/runs/3351485580
    ```
    Reproduce failed and passed jobs:
    ``` shell
    (venv) ~/actions-remaker$ bash run.sh -r Grasscutters/Grasscutter -f 9179386809 -p 9179402125
    ```
    View reproduced failed job log:
    ```shell
    (venv) ~/actions-remaker$ cat reproducer/output/tasks/task/Grasscutters/Grasscutter/-1-3344953329-3351485580/9179386809-9179402125/9179386809.log
    ```
    View reproduced passed job log:
    ```shell
    (venv) ~/actions-remaker$ cat reproducer/output/tasks/task/Grasscutters/Grasscutter/-1-3344953329-3351485580/9179386809-9179402125/9179402125.log
    ```
    Check newly generated Docker images:
    ```shell
    (venv) ~/actions-remaker$ docker image ls
    REPOSITORY                         TAG                                       IMAGE ID       CREATED              SIZE
    job_id                             9179402125                                c9421d72ee0e   About a minute ago   11.6GB
    job_id                             9179386809                                086391da557b   About a minute ago   11.6GB
    ```
2. Reproduce just the [failed job](https://github.com/Grasscutters/Grasscutter/actions/runs/3344953329/jobs/5552953144) [(original log)](reproducer/intermediates/orig_logs/9179386809-orig.log).
    ``` shell
    (venv) ~/actions-remaker$ bash run.sh -r Grasscutters/Grasscutter -j 9179386809
    ```
