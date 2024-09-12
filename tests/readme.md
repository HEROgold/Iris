# README

## Command

cd src
pytest .\tests\ --file c:\\Users\\marti\\Documents\\GitHub\\Iris\\rom.smc

## Required Information

When a writing test fails, all tests ran after that one, will also fail.
They test if the original file and new file are the exact same, so when one test fails,
all others fail too.

Find the first test that failed, and that's where you should start fixing.
