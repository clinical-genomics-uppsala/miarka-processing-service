#!/bin/bash

set -euxo pipefail

echo "RUNNING: wp1 GMS560";

# Initialize variables
inbox_path=""

# Process options and arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --inbox-path)
            inbox_path="$2"
            shift 2
            ;;
        *)
            echo "Error: Unknown option or missing argument: $1"
            exit 1
            ;;
    esac
done

# Check if required options are provided
if [ -z "$inbox_path" ]; then
    echo "Error: --inbox-path is required.";
    exit 2;
fi

i=0
sleep 3
while [ $i -le 5 ];
do
	echo "Still running some analysis.."
	sleep 2
	i=$((i + 1))
done

echo "ANALYSIS DONE: wp1 GMS560";


