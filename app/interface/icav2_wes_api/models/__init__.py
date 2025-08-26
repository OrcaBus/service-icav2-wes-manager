from typing import Literal

# ICAv2 constants
AnalysisStorageSizeType = Literal[
    'SMALL', 'MEDIUM', 'LARGE',
    'XLARGE', '2XLARGE', '3XLARGE',
]

AnalysisStatusType = Literal[
    'SUBMITTED',
    'PENDING',
    'RUNNABLE',
    'STARTING',
    'RUNNING',
    'SUCCEEDED',
    'FAILED',
    'ABORTED',
]
