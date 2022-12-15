USAGE='Usage: bash get_id.sh <github-url>'

# Check inputs
if [ -z "$1" ]; then
  echo ${USAGE}
  exit 1
fi

python3 get_job_id.py "$1"
