from enum import Enum


class Result(Enum):
    success = 'success',
    skipped = 'skipped',  # try again 24 hours later, do not notify user
    unverified = 'unverified',  # do not try again, notify user of error
    failed = 'failed'  # retry up to 5 times, if still failing then notify user of error after final failure
