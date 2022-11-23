USAGE='Usage: bash run.sh -r <repo-slug> (-f <failed-job-id> -p <passed-job-id> | -j <job-id>)'

OPTS=$(getopt -o r:f:p:j --long repo:,failed-job-id:,passed-job-id:,job-id: -n 'run' -- "$@")
while true; do
  case "$1" in
    # Shift twice for options that take an argument.
    -r | --repo                ) repo="$2";                shift; shift ;;
    -f | --failed-job-id       ) failed_job_id="$2";       shift; shift ;;
    -p | --passed-job-id       ) passed_job_id="$2";       shift; shift ;;
    -j | --job-id              ) job_id="$2";       shift; shift ;;
    -- ) shift; break ;;
    *  ) break ;;
  esac
done

# Check inputs
if [ -z "${repo}" ]; then
  echo ${USAGE}
  exit 1
fi

if [ -z "${job_id}" ]; then
  if [ -z "${failed_job_id}" ]; then
    echo ${USAGE}
    exit 1
  fi

  if [ -z "${passed_job_id}" ]; then
    echo ${USAGE}
    exit 1
  fi
fi


echo 'Generating input file...'
STATUS=0
if [ -z "${job_id}" ]; then
  python3 get_job_input.py "${repo}" "${failed_job_id}" "${passed_job_id}"
  STATUS=$?
else
  python3 get_job_input.py "${repo}" "${job_id}"
  STATUS=$?
fi


if [ $STATUS -ne 0 ]; then
  rm -rf intermediates
  exit 1
else
  rm -rf intermediates
fi


echo 'Running ActionsRemaker...'
if [ -z "${job_id}" ]; then
  echo "Generating new Docker image (job_id:${failed_job_id}, job_id:${passed_job_id})"
else
  echo "Generating new Docker image (job_id:${job_id})"
fi

cd reproducer || exit
python3 entry.py -i task.json -t 8 -k -o task
echo 'Done!'