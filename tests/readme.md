# README

## Command

cd src
pytest .\tests\ --file (rom file)

## Required Information

When a writing test fails, all tests ran after that one, will also fail.
They test if the original file and new file are the exact same, so when one test fails,
all others fail too.

Find the first test that failed, and that's where you should start fixing.
