from enum import Enum


class Result(Enum):
    success = 'success',
    skipped = 'skipped',
    unverified = 'unverified'
