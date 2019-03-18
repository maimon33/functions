#!/usr/bin/env bash

test_ssh ()
{
    for i in 1 2 3 4 5; do echo "Trying SSH" && ssh $1 'echo "Hello from host" && break || sleep 15; done
}
