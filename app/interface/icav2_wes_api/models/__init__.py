from typing import Literal


AnalysisStatus = Literal[
    'SUBMITTED',
    'PENDING',
    'RUNNABLE',
    'STARTING',
    'RUNNING',
    'SUCCEEDED',
    'FAILED',
    'ABORTED',
]
