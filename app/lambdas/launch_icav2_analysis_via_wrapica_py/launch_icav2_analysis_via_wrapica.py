#!/usr/bin/env python3

"""
Launch the ICAv2 analysis.

Given the name, inputs, engine parameters, launch the analysis on ICAv2!
"""
# Standard imports
import json
from copy import copy
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Dict, Optional, cast
from fastapi.encoders import jsonable_encoder

# Wrapica imports
from wrapica.literals import AnalysisStorageSizeType
from wrapica.pipelines import get_pipeline_obj_from_pipeline_id
from wrapica.project_pipelines import (
    ICAv2PipelineAnalysisTags, Analysis
)

# Layer imports
from icav2_tools import set_icav2_env_vars


def camel_case_to_snake_case(camel_case_str: str) -> str:
    # Convert fastqListRowId to fastq_list_row_id
    return ''.join(['_' + i.lower() if i.isupper() else i for i in camel_case_str]).lstrip('_')


def flatten_user_tags(user_tags: Dict) -> Dict:
    user_tags = dict(
        map(
            lambda kv: (camel_case_to_snake_case(kv[0]), kv[1]),
            user_tags.items()
        )
    )

    for key, value in copy(user_tags).items():
        if isinstance(value, list):
            for iter_, value_iter in enumerate(value):
                user_tags[f"{key}.{iter_}"] = value_iter
            del user_tags[key]

    return user_tags


def handler(event, context):
    """
    We expect the following event attributes
      * name
      * inputs
      * engineParameters
      * tags
    :param event:
    :param context:
    :return:
    """

    # Set icav2 env vars
    set_icav2_env_vars()

    # Check if the event has the required attributes
    if not all(key in event for key in ['name', 'inputs', 'engineParameters', 'tags']):
        raise ValueError("Event must contain 'name', 'inputs', 'engineParameters', and 'tags' attributes")

    # Extract the WES attributes from the event
    id_ = event['id']
    name = event['name']
    inputs = event['inputs']
    engine_parameters = event['engineParameters']
    user_tags = event.get('tags', {})
    technical_tags = event.get('technicalTags', None)

    # Get the pipeline id from the engine parameters
    pipeline_id = engine_parameters['pipelineId']

    # Get the project id from the engine parameters
    project_id = engine_parameters['projectId']

    # Get the analysis output uri and ica logs uri from the engine parameters
    analysis_output_uri = engine_parameters['outputUri']
    ica_logs_uri = engine_parameters['logsUri']

    # Get the pipeline object (to get the workflow language type)
    pipeline_obj = get_pipeline_obj_from_pipeline_id(pipeline_id)

    # Get the analysis storage size from the event
    analysis_storage_size: Optional[AnalysisStorageSizeType] = event.get("analysis_storage_size", None)
    if analysis_storage_size is None:
        # Get the default analysis storage size from the pipeline object
        pipeline_obj = get_pipeline_obj_from_pipeline_id(pipeline_id)
        analysis_storage_size = cast(AnalysisStorageSizeType, pipeline_obj.analysis_storage.name)

    # Get the workflow type, one of CWL or NEXTFLOW
    workflow_type = pipeline_obj.language

    # Imports based on workflow type
    if workflow_type.lower() == 'cwl':
        from wrapica.project_pipelines import (
            ICAv2CwlAnalysisJsonInput as ICAv2AnalysisInput,
            ICAv2CWLPipelineAnalysis as ICAv2PipelineAnalysis,
        )
        # Collect the input json
        icav2_analysis_input_obj = ICAv2AnalysisInput(
            input_json=inputs
        )
    elif workflow_type.lower() == 'nextflow':
        from wrapica.project_pipelines import (
            ICAv2NextflowAnalysisInput as ICAv2AnalysisInput,
            ICAv2NextflowPipelineAnalysis as ICAv2PipelineAnalysis,
        )
        # Also get the cache uri from the engine parameters if it exists
        cache_uri = engine_parameters.get('cacheUri', None)

        # Collect the input json
        icav2_analysis_input_obj = ICAv2AnalysisInput(
            input_json=inputs,
            # We may need this in case we have to upload a samplesheet object
            # for nf-core pipelines
            cache_uri=cache_uri
        )
    else:
        raise ValueError(f"workflow_type should be one of 'nextflow' or 'cwl' got {workflow_type} instead")

    # Initialise an ICAv2CWLPipeline Analysis object
    analysis_obj = ICAv2PipelineAnalysis(
        user_reference=name,
        project_id=project_id,
        pipeline_id=pipeline_id,
        analysis_input=icav2_analysis_input_obj.create_analysis_input(),
        analysis_storage_size=analysis_storage_size,
        analysis_output_uri=analysis_output_uri,
        ica_logs_uri=ica_logs_uri,
        tags=ICAv2PipelineAnalysisTags(
            technical_tags=technical_tags,
            user_tags=user_tags,
            reference_tags=[]
        )
    )

    # Generate the inputs and analysis object
    # Call the object to launch it
    analysis_launch_obj: Analysis = analysis_obj(
        idempotency_key=id_
    )

    # Save the analysis
    with NamedTemporaryFile(suffix='.json') as temp_file:
        analysis_obj.save_analysis(Path(temp_file.name))

        with open(Path(temp_file.name), 'r') as tmp_file_h:
            analysis_launch_payload = json.load(tmp_file_h)

    return jsonable_encoder({
        "analysisId": analysis_launch_obj.id,
        "analysisStatus": analysis_launch_obj.status,
        "analysisResponsePayload": analysis_launch_obj.to_dict(),
        "analysisLaunchPayload": analysis_launch_payload
    })


# if __name__ == "__main__":
#     from os import environ
#
#     environ['AWS_REGION'] = 'ap-southeast-2'
#     environ['AWS_PROFILE'] = 'umccr-development'
#     environ['HOSTNAME_SSM_PARAMETER_NAME'] = '/hosted_zone/umccr/name'
#     environ['ORCABUS_TOKEN_SECRET_ID'] = 'orcabus/token-service-jwt'
#     environ['ICAV2_ACCESS_TOKEN_SECRET_ID'] = 'ICAv2JWTKey-umccr-prod-service-dev'
#
#     print(json.dumps(
#         handler(
#             {
#                 "id": "iwa.01K1FWBE8765FGF027XGPF2T3A",
#                 "name": "test-cttsov2-in-icav2-wes-f2-pipeline",
#                 "inputs": {
#                     "run_folder": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/cache/cttsov2/20250612f682d1b9-3/241024_A00130_0336_BHW7MVDSXC/",
#                     "sample_sheet": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/cache/cttsov2/20250612f682d1b9-3/SampleSheet.csv",
#                     "StartsFromFastq": True,
#                     "sample_pair_ids": "L2401531"
#                 },
#                 "engineParameters": {
#                     "pipelineId": "63dc920c-adde-4891-8aae-84a6b9569f37",
#                     "projectId": "ea19a3f5-ec7c-4940-a474-c31cd91dbad4",
#                     "logsUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/test-cttsov2-in-icav2-wes-f2-pipeline/logs/",
#                     "outputUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/test-cttsov2-in-icav2-wes-f2-pipeline/outputs/"
#                 },
#                 "tags": {}
#             },
#             None
#         ),
#         indent=4
#     ))


# # WGTS DNA example
# if __name__ == "__main__":
#     from os import environ
#
#     environ['AWS_REGION'] = 'ap-southeast-2'
#     environ['AWS_PROFILE'] = 'umccr-development'
#     environ['HOSTNAME_SSM_PARAMETER_NAME'] = '/hosted_zone/umccr/name'
#     environ['ORCABUS_TOKEN_SECRET_ID'] = 'orcabus/token-service-jwt'
#     environ['ICAV2_ACCESS_TOKEN_SECRET_ID'] = 'ICAv2JWTKey-umccr-prod-service-dev'
#
#     print(json.dumps(
#         handler(
#             {
#                 "id": "iwa.01K1J6XPPAZYXNVTJCFXJEYV0X",
#                 "name": "umccr--automated--dragen-wgts-dna--4-4-4--20250801fc84a1df",
#                 "inputs": {
#                     "reference": {
#                         "name": "hg38",
#                         "tarball": {
#                             "class": "File",
#                             "location": "s3://pipeline-prod-cache-503977275616-ap-southeast-2/byob-icav2/reference-data/dragen-hash-tables/v11-r5/hg38-alt_masked-cnv-graph-hla-methyl_cg-rna/hg38-alt_masked.cnv.graph.hla.methyl_cg.rna-11-r5.0-1.tar.gz"
#                         },
#                         "structure": "graph"
#                     },
#                     "sample_name": "L2401540",
#                     "ora_reference": {
#                         "class": "File",
#                         "location": "s3://pipeline-prod-cache-503977275616-ap-southeast-2/byob-icav2/reference-data/dragen-ora/v2/ora_reference_v2.tar.gz"
#                     },
#                     "sequence_data": {
#                         "fastq_list_rows": [
#                             {
#                                 "lane": 2,
#                                 "rgcn": "UMCCR",
#                                 "rgds": "Library ID: L2401540 / Sequenced on 24 Oct 2024 at UMCCR / Phenotype: normal / Assay: TsqNano / Type: WGS",
#                                 "rgdt": "2024-10-24",
#                                 "rgid": "GGACTTGG+CGTCTGCG.2.241024_A00130_0336_BHW7MVDSXC",
#                                 "rglb": "L2401540",
#                                 "rgpl": "Illumina",
#                                 "rgsm": "L2401540",
#                                 "read_1": {
#                                     "class": "File",
#                                     "location": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/primary/241024_A00130_0336_BHW7MVDSXC/20250611c473883f/Samples/Lane_2/L2401540/L2401540_S10_L002_R1_001.fastq.ora"
#                                 },
#                                 "read_2": {
#                                     "class": "File",
#                                     "location": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/primary/241024_A00130_0336_BHW7MVDSXC/20250611c473883f/Samples/Lane_2/L2401540/L2401540_S10_L002_R2_001.fastq.ora"
#                                 }
#                             }
#                         ]
#                     },
#                     "tumor_sample_name": "L2401541",
#                     "alignment_options": {
#                         "enable_duplicate_marking": True
#                     },
#                     "somatic_reference": {
#                         "name": "hg38",
#                         "tarball": {
#                             "class": "File",
#                             "location": "s3://pipeline-prod-cache-503977275616-ap-southeast-2/byob-icav2/reference-data/dragen-hash-tables/v11-r5/hg38-alt_masked-cnv-hla-methyl_cg-methylated_combined/hg38-alt_masked.cnv.hla.methyl_cg.methylated_combined.rna-11-r5.0-1.tar.gz"
#                         },
#                         "structure": "linear"
#                     },
#                     "tumor_sequence_data": {
#                         "fastq_list_rows": [
#                             {
#                                 "lane": 2,
#                                 "rgcn": "UMCCR",
#                                 "rgds": "Library ID: L2401541 / Sequenced on 24 Oct 2024 at UMCCR / Phenotype: tumor / Assay: TsqNano / Type: WGS",
#                                 "rgdt": "2024-10-24",
#                                 "rgid": "AAGTCCAA+TACTCATA.2.241024_A00130_0336_BHW7MVDSXC",
#                                 "rglb": "L2401541",
#                                 "rgpl": "Illumina",
#                                 "rgsm": "L2401541",
#                                 "read_1": {
#                                     "class": "File",
#                                     "location": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/primary/241024_A00130_0336_BHW7MVDSXC/20250611c473883f/Samples/Lane_2/L2401541/L2401541_S11_L002_R1_001.fastq.ora"
#                                 },
#                                 "read_2": {
#                                     "class": "File",
#                                     "location": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/primary/241024_A00130_0336_BHW7MVDSXC/20250611c473883f/Samples/Lane_2/L2401541/L2401541_S11_L002_R2_001.fastq.ora"
#                                 }
#                             }
#                         ]
#                     },
#                     "targeted_caller_options": {
#                         "enable_targeted": [
#                             "cyp2d6"
#                         ]
#                     },
#                     "snv_variant_caller_options": {
#                         "qc_detect_contamination": True,
#                         "vc_mnv_emit_component_calls": True,
#                         "vc_combine_phased_variants_distance": 2,
#                         "vc_combine_phased_variants_distance_snvs_only": 2
#                     }
#                 },
#                 "engineParameters": {
#                     "pipelineId": "05cb03fd-aed3-4008-9532-46f97b1f0bc8",
#                     "projectId": "ea19a3f5-ec7c-4940-a474-c31cd91dbad4",
#                     "outputUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/dragen-wgts-dna/20250801fc84a1df/",
#                     "logsUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/logs/dragen-wgts-dna/20250801fc84a1df/"
#                 },
#                 "tags": {
#                     "libraryId": "L2401540",
#                     "subjectId": "9689947",
#                     "individualId": "SBJ05828",
#                     "fastqRgidList": [
#                         "GGACTTGG+CGTCTGCG.2.241024_A00130_0336_BHW7MVDSXC"
#                     ],
#                     "tumorLibraryId": "L2401541",
#                     "tumorFastqRgidList": [
#                         "AAGTCCAA+TACTCATA.2.241024_A00130_0336_BHW7MVDSXC"
#                     ],
#                     "ntsmExternalPassing": True,
#                     "preLaunchDupFracEst": 0.12,
#                     "preLaunchCoverageEst": 46.47,
#                     "preLaunchInsertSizeEst": 286,
#                     "tumorPreLaunchDupFracEst": 0.11,
#                     "tumorPreLaunchCoverageEst": 100.86,
#                     "tumorPreLaunchInsertSizeEst": 286,
#                     "portalRunId": "20250801fc84a1df"  # pragma: allowlist secret
#                 },
#                 "technicalTags": {
#                     "icav2_wes_orcabus_id": "iwa.01K1HYHCZZ7ZS236E6BVTM50WC",
#                     "launch_step_functions_execution_id": "arn:aws:states:ap-southeast-2:843407916570:stateMachine:icav2-wes-launchIcav2Analysis"
#                 }
#             },
#             None
#         ),
#         indent=4
#     ))


# Oncoanalyser 2.0.0 example
# if __name__ == "__main__":
#     from os import environ
#
#     environ['AWS_REGION'] = 'ap-southeast-2'
#     environ['AWS_PROFILE'] = 'umccr-development'
#     environ['HOSTNAME_SSM_PARAMETER_NAME'] = '/hosted_zone/umccr/name'
#     environ['ORCABUS_TOKEN_SECRET_ID'] = 'orcabus/token-service-jwt'
#     environ['ICAV2_ACCESS_TOKEN_SECRET_ID'] = 'ICAv2JWTKey-umccr-prod-service-dev'
#
#     print(json.dumps(
#         handler(
#             {
#                 "id": "iwa.01K1PH9WABMM91D0H7EQJYGBX9",
#                 "name": "umccr--automated--oncoanalyser-wgts-dna--2-0-0--20250801f80c3f7a",
#                 "inputs": {
#                     "mode": "wgts",
#                     "samplesheet": [
#                         # Normal Bam
#                         {
#                             "group_id": "SBJ05828",
#                             "subject_id": "SBJ05828",
#                             "sample_id": "L2401540",
#                             "sample_type": "normal",
#                             "sequence_type": "dna",
#                             "filetype": "bam",
#                             "filepath": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/dragen-wgts-dna/20250801fc84a1df/L2401541__L2401540__hg38__linear__dragen_variant_calling/L2401540_normal.bam",
#                         },
#                         # Normal Bam index
#                         {
#                             "group_id": "SBJ05828",
#                             "subject_id": "SBJ05828",
#                             "sample_id": "L2401540",
#                             "sample_type": "normal",
#                             "sequence_type": "dna",
#                             "filetype": "bai",
#                             "filepath": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/dragen-wgts-dna/20250801fc84a1df/L2401541__L2401540__hg38__linear__dragen_variant_calling/L2401540_normal.bam.bai",
#                         },
#                         # Tumor Bam
#                         {
#                             "group_id": "SBJ05828",
#                             "subject_id": "SBJ05828",
#                             "sample_id": "L2401541",
#                             "sample_type": "tumor",
#                             "sequence_type": "dna",
#                             "filetype": "bam",
#                             "filepath": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/dragen-wgts-dna/20250801fc84a1df/L2401541__L2401540__hg38__linear__dragen_variant_calling/L2401541_tumor.bam",
#                         },
#                         # Tumor Bam index
#                         {
#                             "group_id": "SBJ05828",
#                             "subject_id": "SBJ05828",
#                             "sample_id": "L2401541",
#                             "sample_type": "tumor",
#                             "sequence_type": "dna",
#                             "filetype": "bai",
#                             "filepath": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/dragen-wgts-dna/20250801fc84a1df/L2401541__L2401540__hg38__linear__dragen_variant_calling/L2401541_tumor.bam.bai",
#                         },
#                     ],
#                     "genome": "GRCh38_hmf",
#                     "genome_version": "38",
#                     "genome_type": "no_alt",
#                     "force_genome": True,
#                     "ref_data_hmf_data_path": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/reference-data/hartwig/hmf-reference-data/hmftools/hmf_pipeline_resources.38_v2.0--3/",
#                 },
#                 "engineParameters": {
#                     "pipelineId": "a64126df-d8b2-4ec0-99df-1154f44a74ef",
#                     "projectId": "ea19a3f5-ec7c-4940-a474-c31cd91dbad4",
#                     "outputUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/oncoanalyser-wgts-dna/20250801f80c3f7a/",
#                     "logsUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/logs/oncoanalyser-wgts-dna/20250801f80c3f7a/",
#                     "cacheUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/cache/oncoanalyser-wgts-dna/20250801f80c3f7a/"
#                 },
#                 "tags": {
#                     "libraryId": "L2401540",
#                     "subjectId": "9689947",
#                     "individualId": "SBJ05828",
#                     "fastqRgidList": [
#                         "GGACTTGG+CGTCTGCG.2.241024_A00130_0336_BHW7MVDSXC"
#                     ],
#                     "tumorLibraryId": "L2401541",
#                     "tumorFastqRgidList": [
#                         "AAGTCCAA+TACTCATA.2.241024_A00130_0336_BHW7MVDSXC"
#                     ],
#                     "portalRunId": "20250801f80c3f7a"  # pragma: allowlist secret
#                 },
#                 "technicalTags": {
#                     "icav2_wes_orcabus_id": "iwa.01K1PH9WABMM91D0H7EQJYGBX9",
#                     "launch_step_functions_execution_id": "arn:aws:states:ap-southeast-2:843407916570:stateMachine:icav2-wes-launchIcav2Analysis"
#                 }
#             },
#             None
#         ),
#         indent=4
#     ))


# Oncoanalyser 2.1.0 example
# if __name__ == "__main__":
#     from os import environ
#
#     environ['AWS_REGION'] = 'ap-southeast-2'
#     environ['AWS_PROFILE'] = 'umccr-development'
#     environ['HOSTNAME_SSM_PARAMETER_NAME'] = '/hosted_zone/umccr/name'
#     environ['ORCABUS_TOKEN_SECRET_ID'] = 'orcabus/token-service-jwt'
#     environ['ICAV2_ACCESS_TOKEN_SECRET_ID'] = 'ICAv2JWTKey-umccr-prod-service-dev'
#
#     print(json.dumps(
#         handler(
#             {
#                 "id": "iwa.01K1M60XE7ZAD8QP8W9VD1X51G",
#                 "name": "umccr--automated--oncoanalyser-wgts-dna--2-1-0--202508017c7ce532",
#                 "inputs": {
#                     "mode": "wgts",
#                     "samplesheet": [
#                         # Normal Bam
#                         {
#                             "group_id": "SBJ05828",
#                             "subject_id": "SBJ05828",
#                             "sample_id": "L2401540",
#                             "sample_type": "normal",
#                             "sequence_type": "dna",
#                             "filetype": "bam",
#                             "filepath": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/dragen-wgts-dna/20250801fc84a1df/L2401541__L2401540__hg38__linear__dragen_variant_calling/L2401540_normal.bam",
#                         },
#                         # Normal Bam index
#                         {
#                             "group_id": "SBJ05828",
#                             "subject_id": "SBJ05828",
#                             "sample_id": "L2401540",
#                             "sample_type": "normal",
#                             "sequence_type": "dna",
#                             "filetype": "bai",
#                             "filepath": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/dragen-wgts-dna/20250801fc84a1df/L2401541__L2401540__hg38__linear__dragen_variant_calling/L2401540_normal.bam.bai",
#                         },
#                         # Tumor Bam
#                         {
#                             "group_id": "SBJ05828",
#                             "subject_id": "SBJ05828",
#                             "sample_id": "L2401541",
#                             "sample_type": "tumor",
#                             "sequence_type": "dna",
#                             "filetype": "bam",
#                             "filepath": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/dragen-wgts-dna/20250801fc84a1df/L2401541__L2401540__hg38__linear__dragen_variant_calling/L2401541_tumor.bam",
#                         },
#                         # Tumor Bam index
#                         {
#                             "group_id": "SBJ05828",
#                             "subject_id": "SBJ05828",
#                             "sample_id": "L2401541",
#                             "sample_type": "tumor",
#                             "sequence_type": "dna",
#                             "filetype": "bai",
#                             "filepath": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/dragen-wgts-dna/20250801fc84a1df/L2401541__L2401540__hg38__linear__dragen_variant_calling/L2401541_tumor.bam.bai",
#                         },
#                     ],
#                     "genome": "GRCh38_hmf",
#                     "genome_version": "38",
#                     "genome_type": "no_alt",
#                     "force_genome": True,
#                     "ref_data_hmf_data_path": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/reference-data/hartwig/hmf-reference-data/hmftools/hmf_pipeline_resources.38_v2.1.0--1/",
#                 },
#                 "engineParameters": {
#                     "pipelineId": "ab6e1d62-1b5a-4b24-86b8-81ccf4bdc7a2",
#                     "projectId": "ea19a3f5-ec7c-4940-a474-c31cd91dbad4",
#                     "outputUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/oncoanalyser-wgts-dna/202508017c7ce532/",
#                     "logsUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/logs/oncoanalyser-wgts-dna/202508017c7ce532/",
#                     "cacheUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/cache/oncoanalyser-wgts-dna/202508017c7ce532/"
#                 },
#                 "tags": {
#                     "libraryId": "L2401540",
#                     "subjectId": "9689947",
#                     "individualId": "SBJ05828",
#                     "fastqRgidList": [
#                         "GGACTTGG+CGTCTGCG.2.241024_A00130_0336_BHW7MVDSXC"
#                     ],
#                     "tumorLibraryId": "L2401541",
#                     "tumorFastqRgidList": [
#                         "AAGTCCAA+TACTCATA.2.241024_A00130_0336_BHW7MVDSXC"
#                     ],
#                     "portalRunId": "202508017c7ce532"  # pragma: allowlist secret
#                 },
#                 "technicalTags": {
#                     "icav2_wes_orcabus_id": "iwa.01K1HYSCNTSK4MV3H49ZXDQPV1",
#                     "launch_step_functions_execution_id": "arn:aws:states:ap-southeast-2:843407916570:stateMachine:icav2-wes-launchIcav2Analysis"
#                 }
#             },
#             None
#         ),
#         indent=4
#     ))


# Sash 0.6.0 (with oncoanalyser 2.0.0 inputs) example  # TODO
# if __name__ == "__main__":
#     from os import environ
#
#     environ['AWS_REGION'] = 'ap-southeast-2'
#     environ['AWS_PROFILE'] = 'umccr-development'
#     environ['HOSTNAME_SSM_PARAMETER_NAME'] = '/hosted_zone/umccr/name'
#     environ['ORCABUS_TOKEN_SECRET_ID'] = 'orcabus/token-service-jwt'
#     environ['ICAV2_ACCESS_TOKEN_SECRET_ID'] = 'ICAv2JWTKey-umccr-prod-service-dev'
#
#     print(json.dumps(
#         handler(
#             {
#                 "id": "iwa.01K1PHM8ZJEN7A4JAPCJPC6NJZ",
#                 "name": "umccr--automated--sash--0-6-0--202508014307def8",
#                 "inputs": {
#                     "monochrome_logs": True,
#                     "samplesheet": [
#                         {
#                           "id": "L2401541_L2401540",
#                           "subject_name": "SBJ05828",
#                           "sample_name": "L2401541",
#                           "filetype": "dragen_somatic_dir",
#                           "filepath": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/dragen-wgts-dna/20250801fc84a1df/L2401541__L2401540__hg38__linear__dragen_variant_calling/"
#                         },
#                         {
#                           "id": "L2401541_L2401540",
#                           "subject_name": "SBJ05828",
#                           "sample_name": "L2401540",
#                           "filetype": "dragen_germline_dir",
#                           "filepath": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/dragen-wgts-dna/20250801fc84a1df/L2401540__hg38__graph__dragen_variant_calling/"
#                         },
#                         {
#                           "id": "L2401541_L2401540",
#                           "subject_name": "SBJ05828",
#                           "sample_name": "L2401541",
#                           "filetype": "oncoanalyser_dir",
#                           "filepath": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/oncoanalyser-wgts-dna/20250801f80c3f7a/SBJ05828/"
#                         }
#                     ],
#                     "ref_data_path": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/reference-data/hartwig/hmf-reference-data/hmftools/hmf_pipeline_resources.38_v2.0--3/"
#                 },
#                 "engineParameters": {
#                     "pipelineId": "57edb806-79f2-4b53-a154-27c4db342485",
#                     "projectId": "ea19a3f5-ec7c-4940-a474-c31cd91dbad4",
#                     "outputUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/sash/202508014307def8/",
#                     "logsUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/logs/sash/202508014307def8/",
#                     "cacheUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/cache/sash/202508014307def8/"
#                 },
#                 "tags": {
#                     "libraryId": "L2401540",
#                     "subjectId": "9689947",
#                     "individualId": "SBJ05828",
#                     "fastqRgidList": [
#                         "GGACTTGG+CGTCTGCG.2.241024_A00130_0336_BHW7MVDSXC"
#                     ],
#                     "tumorLibraryId": "L2401541",
#                     "tumorFastqRgidList": [
#                         "AAGTCCAA+TACTCATA.2.241024_A00130_0336_BHW7MVDSXC"
#                     ],
#                     "portalRunId": "202508014307def8"  # pragma: allowlist secret
#                 },
#                 "technicalTags": {
#                     "icav2_wes_orcabus_id": "iwa.01K1PHM8ZJEN7A4JAPCJPC6NJZ",
#                     "launch_step_functions_execution_id": "arn:aws:states:ap-southeast-2:843407916570:stateMachine:icav2-wes-launchIcav2Analysis"
#                 }
#             },
#             None
#         ),
#         indent=4
#     ))

# # Sash 0.6.0 (with oncoanalyser 2.1.0 inputs) example
# if __name__ == "__main__":
#     from os import environ
#
#     environ['AWS_REGION'] = 'ap-southeast-2'
#     environ['AWS_PROFILE'] = 'umccr-development'
#     environ['HOSTNAME_SSM_PARAMETER_NAME'] = '/hosted_zone/umccr/name'
#     environ['ORCABUS_TOKEN_SECRET_ID'] = 'orcabus/token-service-jwt'
#     environ['ICAV2_ACCESS_TOKEN_SECRET_ID'] = 'ICAv2JWTKey-umccr-prod-service-dev'
#
#     print(json.dumps(
#         handler(
#             {
#                 "id": "iwa.01K1PFWRHE37P32H31V1P5836Y",
#                 "name": "umccr--automated--sash--0-6-0--20250801fadd4c1e",
#                 "inputs": {
#                     "monochrome_logs": True,
#                     "samplesheet": [
#                         {
#                           "id": "L2401541_L2401540",
#                           "subject_name": "SBJ05828",
#                           "sample_name": "L2401541",
#                           "filetype": "dragen_somatic_dir",
#                           "filepath": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/dragen-wgts-dna/20250801fc84a1df/L2401541__L2401540__hg38__linear__dragen_variant_calling/"
#                         },
#                         {
#                           "id": "L2401541_L2401540",
#                           "subject_name": "SBJ05828",
#                           "sample_name": "L2401540",
#                           "filetype": "dragen_germline_dir",
#                           "filepath": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/dragen-wgts-dna/20250801fc84a1df/L2401540__hg38__graph__dragen_variant_calling/"
#                         },
#                         {
#                           "id": "L2401541_L2401540",
#                           "subject_name": "SBJ05828",
#                           "sample_name": "L2401541",
#                           "filetype": "oncoanalyser_dir",
#                           "filepath": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/oncoanalyser-wgts-dna/202508017c7ce532/SBJ05828/"
#                         }
#                     ],
#                     "ref_data_path": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/reference-data/hartwig/hmf-reference-data/hmftools/hmf_pipeline_resources.38_v2.1.0--1/"
#                 },
#                 "engineParameters": {
#                     "pipelineId": "57edb806-79f2-4b53-a154-27c4db342485",
#                     "projectId": "ea19a3f5-ec7c-4940-a474-c31cd91dbad4",
#                     "outputUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/sash/20250801fadd4c1e/",
#                     "logsUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/logs/sash/20250801fadd4c1e/",
#                     "cacheUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/cache/sash/20250801fadd4c1e/"
#                 },
#                 "tags": {
#                     "libraryId": "L2401540",
#                     "subjectId": "9689947",
#                     "individualId": "SBJ05828",
#                     "fastqRgidList": [
#                         "GGACTTGG+CGTCTGCG.2.241024_A00130_0336_BHW7MVDSXC"
#                     ],
#                     "tumorLibraryId": "L2401541",
#                     "tumorFastqRgidList": [
#                         "AAGTCCAA+TACTCATA.2.241024_A00130_0336_BHW7MVDSXC"
#                     ],
#                     "portalRunId": "20250801fadd4c1e"  # pragma: allowlist secret
#                 },
#                 "technicalTags": {
#                     "icav2_wes_orcabus_id": "iwa.01K1PFWRHE37P32H31V1P5836Y",
#                     "launch_step_functions_execution_id": "arn:aws:states:ap-southeast-2:843407916570:stateMachine:icav2-wes-launchIcav2Analysis"
#                 }
#             },
#             None
#         ),
#         indent=4
#     ))
