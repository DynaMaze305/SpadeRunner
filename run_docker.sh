#!/bin/bash

set -e

TEST_MODE=false
PROSODY_MODE=false
LOCAL_MODE=true

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --test)
            TEST_MODE=true
            ;;
        --test-prosody)
            PROSODY_MODE=true
            TEST_MODE=true
            ;;
        --local)
            LOCAL_MODE=true
            ;;
        --alphabot)
            LOCAL_MODE=false
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
    shift
done

# Remove past docker
sudo docker rm -f spaderunner-app spaderunner-agent spaderunner-prosody 2>/dev/null
sudo docker rmi -f spaderunner-app spaderunner-agent spaderunner-prosody 2>/dev/null

# Start prosody if needed
if [ "$PROSODY_MODE" = true ]; then
    echo "Launching prosody (test)"
    sudo docker compose up prosody --build -d
fi

# Test mode
if [ "$TEST_MODE" = true ]; then
    echo "Launching app (test)"
    sudo docker compose up app --build

    if [ "$PROSODY_MODE" = true ]; then
        echo "Stopping prosody (test)"
        sudo docker stop spaderunner-prosody
    fi

    exit 0
fi

# Normal mode
if [ "$LOCAL_MODE" = true ]; then
    sudo docker compose up local --build
else
    sudo docker compose up alphabot --build
fi

# Stop prosody if it was started
if [ "$PROSODY_MODE" = true ]; then
    echo "Stopping prosody"
    sudo docker stop spaderunner-prosody
fi
