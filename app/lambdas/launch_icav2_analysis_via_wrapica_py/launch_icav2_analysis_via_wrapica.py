#!/usr/bin/env python3

"""
Launch the ICAv2 analysis.

Given the name, inputs, engine parameters, launch the analysis on ICAv2!
"""

# Standard imports
import typing
from copy import copy
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Dict, Optional, cast, Literal
from fastapi.encoders import jsonable_encoder
import boto3
from datetime import datetime, timezone
from urllib.parse import urlunparse
import gzip
from time import sleep
import logging
from os import environ

# Wrapica imports
from wrapica.literals import AnalysisStorageSizeType
from wrapica.project_pipelines import (
    ICAv2PipelineAnalysisTags,
    get_project_pipeline_obj
)

# Layer imports
from icav2_tools import set_icav2_env_vars

# Type hints
if typing.TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Globals
# WES Storage sizes constants
WesAnalysisStorageSizeType = Literal[
    'SMALL', 'MEDIUM', 'LARGE',
    'XLARGE', '2XLARGE', '3XLARGE',
]


# Custom errors
class CreateAnalysisInputFailure(Exception):
    pass


class AnalysisLaunchFailure(Exception):
    pass


class PipelineNotFoundFailure(Exception):
    pass


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


def map_wes_analysis_storage_size_to_icav2(storage_size: WesAnalysisStorageSizeType) -> AnalysisStorageSizeType:
    """
    Map the WES analysis storage size to the ICAv2 analysis storage size.
    :param storage_size: The WES analysis storage size.
    :return: The ICAv2 analysis storage size.
    """
    mapping: Dict[WesAnalysisStorageSizeType, AnalysisStorageSizeType] = {
        'SMALL': 'Small',
        'MEDIUM': 'Medium',
        'LARGE': 'Large',
        'XLARGE': 'XLarge',
        '2XLARGE': '2XLarge',
        '3XLARGE': '3XLarge',
    }
    return mapping[storage_size]


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
        raise ValueError("Event must contain 'name', 'inputs', 'engineParameters' and 'tags' attributes")

    # Extract the WES attributes from the event
    id_ = event['id']
    name = event['name']
    inputs = event['inputs']
    engine_parameters = event['engineParameters']
    user_tags = flatten_user_tags(event.get('tags', {}))
    technical_tags = event.get('technicalTags', None)

    # Get the pipeline id from the engine parameters
    pipeline_id = engine_parameters['pipelineId']

    # Get the project id from the engine parameters
    project_id = engine_parameters['projectId']

    # Get the analysis output uri and ica logs uri from the engine parameters
    analysis_output_uri = engine_parameters['outputUri']
    ica_logs_uri = engine_parameters['logsUri']

    # Get the pipeline object (to get the workflow language type)
    logger.info("Getting the pipeline object")
    try:
        pipeline_obj = get_project_pipeline_obj(
            project_id=project_id,
            pipeline_id=pipeline_id
        ).pipeline
    except Exception as e:
        logger.error(f"Error getting the pipeline object: {e}")
        raise PipelineNotFoundFailure(f"Pipeline with id {pipeline_id} not found in project {project_id}") from e

    # Get the analysis storage size from the event
    logger.info("Getting the analysis storage size")
    wes_analysis_storage_size: Optional[WesAnalysisStorageSizeType] = engine_parameters.get("analysisStorageSize", None)
    if wes_analysis_storage_size is not None:
        analysis_storage_size: AnalysisStorageSizeType = map_wes_analysis_storage_size_to_icav2(
            wes_analysis_storage_size)
    else:
        # Get the default analysis storage size from the pipeline object
        analysis_storage_size = cast(AnalysisStorageSizeType, pipeline_obj.analysis_storage.name)

    # Get the workflow type, one of CWL or NEXTFLOW
    workflow_type = pipeline_obj.language

    # Imports based on workflow type
    logger.info("Generating the ICAv2 Analysis Input Object")
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
    logger.info("Generating the analysis object")
    try:
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
    except Exception as e:
        logger.error(f"Error generating the analysis object: {e}")
        raise CreateAnalysisInputFailure("Failed to create analysis input object") from e

    # Wait a few seconds for the samplesheet to be available in ICAv2
    sleep(5)

    # Generate the inputs and analysis object
    # Call the object to launch it
    logger.info("Launching the analysis object")
    try:
        analysis_launch_obj = analysis_obj(
            idempotency_key=id_
        )
    except Exception as e:
        logger.error(f"Error launching the analysis object: {e}")
        raise AnalysisLaunchFailure("Failed to launch analysis") from e

    # Get the current date and upload path
    logger.info("Uploading the analysis launch object to S3")
    now = datetime.now(timezone.utc)
    upload_path = str(
        Path(environ['S3_ANALYSIS_PAYLOAD_KEY_PREFIX']) /
        f"year={now.year}" /
        f"month={now.month:02d}" /
        f"day={now.day:02d}" /
        f"{analysis_launch_obj.id}.json.gz"
    )

    # Save the analysis object to a temporary file
    with (
        NamedTemporaryFile(suffix='.json') as temp_file_json,
        NamedTemporaryFile(suffix='.json.gz') as temp_file_gz
    ):
        # Save and flush to first json
        analysis_obj.save_analysis(Path(temp_file_json.name))
        temp_file_json.flush()

        # Gzip compress the analysis json
        with gzip.GzipFile(fileobj=temp_file_gz, mode="wb") as gz_file:
            # Now go back to the start of the json file and write to gz
            temp_file_json.seek(0)
            gz_file.write(temp_file_json.read())

        # Write out the gzip file to the temp file
        temp_file_gz.flush()

        # Upload the analysis json to S3
        s3_client: 'S3Client' = boto3.client('s3')
        s3_client.upload_file(
            Filename=temp_file_gz.name,
            Bucket=environ['S3_ANALYSIS_ARTEFACTS_BUCKET_NAME'],
            Key=upload_path
        )

    s3_payload_uri = str(urlunparse((
        's3',
        environ['S3_ANALYSIS_ARTEFACTS_BUCKET_NAME'],
        str(upload_path),
        None, None, None
    )))

    logger.info("Finished launching the analysis")

    return jsonable_encoder({
        "analysisId": analysis_launch_obj.id,
        "analysisStatus": analysis_launch_obj.status,
        "analysisResponsePayload": analysis_launch_obj.to_dict(),
        "analysisLaunchPayloadUri": s3_payload_uri
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
#     import json
#
#     environ['AWS_REGION'] = 'ap-southeast-2'
#     environ['AWS_PROFILE'] = 'umccr-development'
#     environ['HOSTNAME_SSM_PARAMETER_NAME'] = '/hosted_zone/umccr/name'
#     environ['ORCABUS_TOKEN_SECRET_ID'] = 'orcabus/token-service-jwt'
#     environ['ICAV2_ACCESS_TOKEN_SECRET_ID'] = 'ICAv2JWTKey-umccr-prod-service-dev'
#     set_icav2_env_vars()
#
#     print(json.dumps(
#         handler(
#             {
#                 "id": "iwa.01K941QFHYZFG03XWXW1JXFA6S",
#                 "name": "umccr--automated--dragen-wgts-dna--4-4-6--2025110380df4ebf",
#                 "inputs": {
#                     "alignment_options": {
#                         "enable_duplicate_marking": True,
#                         "qc_coverage": [
#                             {
#                                 "name": "fcc",
#                                 "region": {
#                                     "class": "File",
#                                     "location": "s3://reference-data-503977275616-ap-southeast-2/refdata/gene-panels/v2--0/germline/umccr_predisposition_genes.transcript_regions.bed"
#                                 },
#                                 "report_type": "cov_report"
#                             },
#                             {
#                                 "name": "umccr",
#                                 "region": {
#                                     "class": "File",
#                                     "location": "s3://reference-data-503977275616-ap-southeast-2/refdata/gene-panels/v2--0/somatic/umccr_cancer_genes.gene_regions.bed"
#                                 },
#                                 "report_type": "cov_report"
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
#                         "vc_combine_phased_variants_distance_snvs_only": 2,
#                         "vc_combine_phased_variants_distance": 2
#                     },
#                     "somatic_cnv_caller_options": {
#                         "enable_cnv": True,
#                         "enable_hrd": True,
#                         "cnv_use_somatic_vc_baf": True,
#                         "cnv_enable_ref_calls": True,
#                     },
#                     "somatic_sv_caller_options": {
#                         "enable_sv": True
#                     },
#                     "somatic_msi_options": {
#                         "msi_command": "tumor-normal",
#                         "msi_microsatellites_file": {
#                             "class": "File",
#                             "location": "s3://reference-data-503977275616-ap-southeast-2/refdata/dragen-msi/1-1-0/hg38/WGS_v1.1.0_hg38_microsatellites.list"
#                         },
#                         "msi_coverage_threshold": 40
#                     },
#                     "somatic_nirvana_annotation_options": {
#                         "enable_variant_annotation": True,
#                         "variant_annotation_assembly": "GRCh38",
#                         "variant_annotation_data": {
#                             "class": "File",
#                             "location": "s3://reference-data-503977275616-ap-southeast-2/refdata/dragen-annotations/nirvana/3.25.1/nirvana_assembly_GRCh38.tar.gz"
#                         }
#                     },
#                     "somatic_tmb_options": {
#                         "enable_tmb": True
#                     },
#                     "sequence_data": {
#                         "fastq_list_rows": [
#                             {
#                                 "lane": 1,
#                                 "rgcn": "UMCCR",
#                                 "rgds": "Library ID: L2101214 / Sequenced on 1 Nov 2021 at UMCCR / Phenotype: normal / Assay: TsqNano / Type: WGS",
#                                 "rgdt": "2021-11-01",
#                                 "rgid": "GGCATTCT+CAAGCTAG.1.211101_A01052_0062_AHLG2LDSX2",
#                                 "rglb": "L2101214",
#                                 "rgpl": "Illumina",
#                                 "rgsm": "L2101214",
#                                 "read_1": {"class": "File", "location": "https://project-data-889522050439-ap-southeast-2.s3.ap-southeast-2.amazonaws.com/byob-icav2/project-wgs-accreditation/primary/fastq/211101_A01052_0062_AHLG2LDSX2/Lane_1/L2101214/MDX210354_L2101214_S1_L001_R2_001.fastq.ora?x-id=GetObject&response-content-disposition=inline&X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=AKIAW32GR4BDNLLYZ76R%2F20251031%2Fap-southeast-2%2Fs3%2Faws4_request&X-Amz-Date=20251031T034842Z&X-Amz-Expires=604800&X-Amz-SignedHeaders=host&X-Amz-Signature=62fce97b130d51041e4d22f2d9040abe971e02b66864053d9a07d284147c066a"},
#                                 "read_2": {"class": "File", "location": "https://project-data-889522050439-ap-southeast-2.s3.ap-southeast-2.amazonaws.com/byob-icav2/project-wgs-accreditation/primary/fastq/211101_A01052_0062_AHLG2LDSX2/Lane_1/L2101214/MDX210354_L2101214_S1_L001_R1_001.fastq.ora?x-id=GetObject&response-content-disposition=inline&X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=AKIAW32GR4BDNLLYZ76R%2F20251031%2Fap-southeast-2%2Fs3%2Faws4_request&X-Amz-Date=20251031T034842Z&X-Amz-Expires=604800&X-Amz-SignedHeaders=host&X-Amz-Signature=f5c83f8bf139fc729429064bd29d4e1cc0e4bea3b4d0a55bfd8791a10fce9c97"}
#                             }
#                         ]
#                     },
#                     "tumor_sequence_data": {
#                         "fastq_list_rows":  [
#                             {
#                                 "lane": 1,
#                                 "rgcn": "UMCCR",
#                                 "rgds": "Library ID: L2101215 / Sequenced on 1 Nov 2021 at UMCCR / Phenotype: tumor / Assay: TsqNano / Type: WGS",
#                                 "rgdt": "2021-11-01",
#                                 "rgid": "AATGCCTC+TGGATCGA.1.211101_A01052_0062_AHLG2LDSX2",
#                                 "rglb": "L2101215",
#                                 "rgpl": "Illumina",
#                                 "rgsm": "L2101215",
#                                 "read_1": {"class": "File", "location": "https://project-data-889522050439-ap-southeast-2.s3.ap-southeast-2.amazonaws.com/byob-icav2/project-wgs-accreditation/primary/fastq/211101_A01052_0062_AHLG2LDSX2/Lane_1/L2101215/MDX210355_L2101215_S2_L001_R2_001.fastq.ora?x-id=GetObject&response-content-disposition=inline&X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=AKIAW32GR4BDNLLYZ76R%2F20251031%2Fap-southeast-2%2Fs3%2Faws4_request&X-Amz-Date=20251031T034924Z&X-Amz-Expires=604800&X-Amz-SignedHeaders=host&X-Amz-Signature=fa7257ffe34bf9bed9cc3865b899745f12b4ab429f95b9578580c529f978cf0b"},
#                                 "read_2": {"class": "File", "location": "https://project-data-889522050439-ap-southeast-2.s3.ap-southeast-2.amazonaws.com/byob-icav2/project-wgs-accreditation/primary/fastq/211101_A01052_0062_AHLG2LDSX2/Lane_1/L2101215/MDX210355_L2101215_S2_L001_R1_001.fastq.ora?x-id=GetObject&response-content-disposition=inline&X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=AKIAW32GR4BDNLLYZ76R%2F20251031%2Fap-southeast-2%2Fs3%2Faws4_request&X-Amz-Date=20251031T034924Z&X-Amz-Expires=604800&X-Amz-SignedHeaders=host&X-Amz-Signature=cb99f95a0c312fa6ab0cfae4796604a0562410ba09c76ffd4b88bc1df9ccaa22"}
#                             }
#                         ]
#                     },
#                     "sample_name": "L2101214",
#                     "tumor_sample_name": "L2101215",
#                     "reference": {
#                         "name": "hg38",
#                         "structure": "graph",
#                         "tarball": {
#                             "class": "File",
#                             "location": "s3://reference-data-503977275616-ap-southeast-2/refdata/dragen-hash-tables/v11-r5/hg38-alt_masked-cnv-graph-hla-methyl_cg-rna/hg38-alt_masked.cnv.graph.hla.methyl_cg.rna-11-r5.0-1.tar.gz"
#                         }
#                     },
#                     "somatic_reference": {
#                         "name": "hg38",
#                         "structure": "linear",
#                         "tarball": {
#                             "class": "File",
#                             "location": "s3://reference-data-503977275616-ap-southeast-2/refdata/dragen-hash-tables/v11-r5/hg38-alt_masked-cnv-hla-methyl_cg-methylated_combined/hg38-alt_masked.cnv.hla.methyl_cg.methylated_combined.rna-11-r5.0-1.tar.gz"
#                         }
#                     },
#                     "ora_reference": {
#                         "class": "File",
#                         "location": "s3://reference-data-503977275616-ap-southeast-2/refdata/dragen-ora/v2/ora_reference_v2.tar.gz"
#                     }
#                 },
#                 "engineParameters": {
#                     "pipelineId": "058d5bb0-3d74-4467-827b-413d1f430ddd",
#                     "projectId": "ea19a3f5-ec7c-4940-a474-c31cd91dbad4",
#                     "outputUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/dragen-wgts-dna/2025110380df4ebf/",
#                     "logsUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/logs/dragen-wgts-dna/2025110380df4ebf/"
#                 },
#                 "tags": {
#                     "libraryId": "L2101214",
#                     "subjectId": "PM9092017",
#                     "individualId": "SBJ01046",
#                     "fastqRgidList": [
#                         "GGCATTCT+CAAGCTAG.1.211101_A01052_0062_AHLG2LDSX2"
#                     ],
#                     "tumorLibraryId": "L2101215",
#                     "tumorFastqRgidList": [
#                         "AATGCCTC+TGGATCGA.1.211101_A01052_0062_AHLG2LDSX2"
#                     ],
#                     "ntsmExternalPassing": True,
#                     "preLaunchDupFracEst": 0.14,
#                     "preLaunchCoverageEst": 49.67,
#                     "preLaunchInsertSizeEst": 286,
#                     "tumorPreLaunchDupFracEst": 0.13,
#                     "tumorPreLaunchCoverageEst": 102.87,
#                     "tumorPreLaunchInsertSizeEst": 286
#                 },
#                 "technicalTags": {
#                     "icav2_wes_orcabus_id": "iwa.01K941QFHYZFG03XWXW1JXFA6S",
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
    #                 "id": "iwa.01K1W3QFCXYTWNZSH8FV3HBD1R",
    #                 "name": "umccr--automated--oncoanalyser-wgts-dna--2-0-0--202508052d182ed9",
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
    #                     "genome": "GRCh38_umccr",
    #                     "genome_version": "38",
    #                     "genome_type": "alt",
    #                     "force_genome": True,
    #                     "ref_data_hmf_data_path": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/reference-data/hartwig/hmf-reference-data/hmftools/hmf_pipeline_resources.38_v2.0--3/",
    #                     "genomes": {
    #                         "GRCh38_umccr": {
    #                             "fasta": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/reference-data/genomes/GRCh38_umccr/GRCh38_full_analysis_set_plus_decoy_hla.fa",
    #                             "fai": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/reference-data/genomes/GRCh38_umccr/samtools_index/1.16/GRCh38_full_analysis_set_plus_decoy_hla.fa.fai",
    #                             "dict": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/reference-data/genomes/GRCh38_umccr/samtools_index/1.16/GRCh38_full_analysis_set_plus_decoy_hla.fa.dict",
    #                             "img": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/reference-data/genomes/GRCh38_umccr/bwa_index_image/0.7.17-r1188/GRCh38_full_analysis_set_plus_decoy_hla.fa.img",
    #                             "bwamem2_index": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/reference-data/genomes/GRCh38_umccr/bwa-mem2_index/2.2.1/",
    #                             "gridss_index": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/reference-data/genomes/GRCh38_umccr/gridss_index/2.13.2/",
    #                             "star_index": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/reference-data/genomes/GRCh38_umccr/star_index/gencode_38/2.7.3a/"
    #                         }
    #                     }
    #                 },
    #                 "engineParameters": {
    #                     "pipelineId": "a64126df-d8b2-4ec0-99df-1154f44a74ef",
    #                     "projectId": "ea19a3f5-ec7c-4940-a474-c31cd91dbad4",
    #                     "outputUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/oncoanalyser-wgts-dna/202508052d182ed9/",
    #                     "logsUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/logs/oncoanalyser-wgts-dna/202508052d182ed9/",
    #                     "cacheUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/cache/oncoanalyser-wgts-dna/202508052d182ed9/"
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
    #                     "portalRunId": "202508052d182ed9"  # pragma: allowlist secret
    #                 },
    #                 "technicalTags": {
    #                     "icav2_wes_orcabus_id": "iwa.01K1W3QFCXYTWNZSH8FV3HBD1R",
    #                     "launch_step_functions_execution_id": "arn:aws:states:ap-southeast-2:843407916570:stateMachine:icav2-wes-launchIcav2Analysis"
    #                 }
    #             },
    #             None
    #         ),
    #         indent=4
    #     ))

    # # Oncoanalyser 2.1.0 example
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
    #                 "id": "iwa.01K1WFV4E9S19FQ856WC93GG6T",
    #                 "name": "umccr--automated--oncoanalyser-wgts-dna--2-1-0--202508052e398fe8",
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
    #                     "genome": "GRCh38_umccr",
    #                     "genome_version": "38",
    #                     "genome_type": "alt",
    #                     "force_genome": True,
    #                     "ref_data_hmf_data_path": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/reference-data/hartwig/hmf-reference-data/hmftools/hmf_pipeline_resources.38_v2.1.0--1/",
    #                     "genomes": {
    #                         "GRCh38_umccr": {
    #                             "fasta": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/reference-data/genomes/GRCh38_umccr/GRCh38_full_analysis_set_plus_decoy_hla.fa",
    #                             "fai": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/reference-data/genomes/GRCh38_umccr/samtools_index/1.16/GRCh38_full_analysis_set_plus_decoy_hla.fa.fai",
    #                             "dict": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/reference-data/genomes/GRCh38_umccr/samtools_index/1.16/GRCh38_full_analysis_set_plus_decoy_hla.fa.dict",
    #                             "img": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/reference-data/genomes/GRCh38_umccr/bwa_index_image/0.7.17-r1188/GRCh38_full_analysis_set_plus_decoy_hla.fa.img",
    #                             "bwamem2_index": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/reference-data/genomes/GRCh38_umccr/bwa-mem2_index/2.2.1/",
    #                             "gridss_index": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/reference-data/genomes/GRCh38_umccr/gridss_index/2.13.2/",
    #                             "star_index": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/reference-data/genomes/GRCh38_umccr/star_index/gencode_38/2.7.3a/"
    #                         }
    #                     }
    #                 },
    #                 "engineParameters": {
    #                     "pipelineId": "ab6e1d62-1b5a-4b24-86b8-81ccf4bdc7a2",
    #                     "projectId": "ea19a3f5-ec7c-4940-a474-c31cd91dbad4",
    #                     "outputUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/oncoanalyser-wgts-dna/202508052e398fe8/",
    #                     "logsUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/logs/oncoanalyser-wgts-dna/202508052e398fe8/",
    #                     "cacheUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/cache/oncoanalyser-wgts-dna/202508052e398fe8/"
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
    #                     "portalRunId": "202508052e398fe8"  # pragma: allowlist secret
    #                 },
    #                 "technicalTags": {
    #                     "icav2_wes_orcabus_id": "iwa.01K1WFV4E9S19FQ856WC93GG6T",
    #                     "launch_step_functions_execution_id": "arn:aws:states:ap-southeast-2:843407916570:stateMachine:icav2-wes-launchIcav2Analysis"
    #                 }
    #             },
    #             None
    #         ),
    #         indent=4
    #     ))

    # Sash 0.6.0 (with oncoanalyser 2.0.0 inputs) example
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
    #                 # "id": "iwa.01K221DJR3G21NA9QD9JKAQDMA",
    #                 "name": "umccr--automated--sash--0-6-0--20250807be72452e",
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
    #                           "filepath": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/oncoanalyser-wgts-dna/202508052d182ed9/SBJ05828/"
    #                         }
    #                     ],
    #                     "ref_data_path": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/reference-data/sash/"
    #                 },
    #                 "engineParameters": {
    #                     "pipelineId": "57edb806-79f2-4b53-a154-27c4db342485",
    #                     "projectId": "ea19a3f5-ec7c-4940-a474-c31cd91dbad4",
    #                     "outputUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/sash/20250807be72452e/",
    #                     "logsUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/logs/sash/20250807be72452e/",
    #                     "cacheUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/cache/sash/20250807be72452e/"
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
    #                     "portalRunId": "202508059f5e8582"  # pragma: allowlist secret
    #                 },
    #                 "technicalTags": {
    #                     "icav2_wes_orcabus_id": "iwa.01K221DJR3G21NA9QD9JKAQDMA",
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
    #                 "id": "iwa.01K291BVRZ4QVWR0K2ZG87FTSB",
    #                 "name": "umccr--automated--sash--0-6-0--20250828b21a4c5c",
    #                 "inputs": {
    #                     "monochrome_logs": True,
    #                     "samplesheet": [
    #                         {
    #                           "id": "L2401541_L2401540",
    #                           "subject_name": "SBJ05828",
    #                           "sample_name": "L2401541",
    #                           "filetype": "dragen_somatic_dir",
    #                           "filepath": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/dragen-wgts-dna/20250809cee5b43a/L2401541__L2401540__hg38__linear__dragen_variant_calling/"
    #                         },
    #                         {
    #                           "id": "L2401541_L2401540",
    #                           "subject_name": "SBJ05828",
    #                           "sample_name": "L2401540",
    #                           "filetype": "dragen_germline_dir",
    #                           "filepath": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/dragen-wgts-dna/20250809cee5b43a/L2401540__hg38__graph__dragen_variant_calling/"
    #                         },
    #                         {
    #                           "id": "L2401541_L2401540",
    #                           "subject_name": "SBJ05828",
    #                           "sample_name": "L2401541",
    #                           "filetype": "oncoanalyser_dir",
    #                           "filepath": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/oncoanalyser-wgts-dna/202508052e398fe8/SBJ05828/"
    #                         }
    #                     ],
    #                     "ref_data_path": "s3://reference-data-503977275616-ap-southeast-2/refdata/sash/0.6.0/"
    #                 },
    #                 "engineParameters": {
    #                     "pipelineId": "57edb806-79f2-4b53-a154-27c4db342485",
    #                     "projectId": "ea19a3f5-ec7c-4940-a474-c31cd91dbad4",
    #                     "outputUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/sash/20250828b21a4c5c/",
    #                     "logsUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/logs/sash/20250828b21a4c5c/",
    #                     "cacheUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/cache/sash/20250828b21a4c5c/"
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
    #                     "portalRunId": "202508101810cf3e"  # pragma: allowlist secret
    #                 },
    #                 "technicalTags": {
    #                     "icav2_wes_orcabus_id": "iwa.01K291BVRZ4QVWR0K2ZG87FTSB",
    #                     "launch_step_functions_execution_id": "arn:aws:states:ap-southeast-2:843407916570:stateMachine:icav2-wes-launchIcav2Analysis"
    #                 }
    #             },
    #             None
    #         ),
    #         indent=4
    #     ))

    # # Oncoanalyser RNA 2.1.0 example
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
    #                 "id": "iwa.01K3QJ0RG3WME99X2DANM1VJVG",
    #                 "name": "umccr--automated--oncoanalyser-wgts-rna--2-1-0--202508285cd658ee",
    #                 "inputs": {
    #                     "mode": "wgts",
    #                     "groupId": "L2500568",
    #                     "subjectId": "L2500568",
    #                     "sampleId": "L2500568",
    #                     "fastqListRows": [
    #                         {
    #                             "rgid": "CGCCATATCT+ATCTCCGGTC.1.250530_A01052_0264_BHFGKTDSXF",
    #                             "rglb": "L2500568",
    #                             "rgsm": "L2500568",
    #                             "lane": 1,
    #                             "rgcn": "UMCCR",
    #                             "rgds": "Library ID: L2500568 / Sequenced on 30 May 2025 at UMCCR / Phenotype: tumor / Assay: ISTRL / Type: WTS",
    #                             "rgdt": "2025-05-30",
    #                             "rgpl": "Illumina",
    #                             "read1FileUri": "s3://test-data-503977275616-ap-southeast-2/testdata/input/fastq/L2500568/L2500568_S1_L001_R1_001.fastq.ora",
    #                             "read2FileUri": "s3://test-data-503977275616-ap-southeast-2/testdata/input/fastq/L2500568/L2500568_S1_L001_R2_001.fastq.ora"
    #                         }
    #                     ],
    #                     "genome": "GRCh38_umccr",
    #                     "genomeVersion": "38",
    #                     "genomeType": "alt",
    #                     "forceGenome": True,
    #                     "refDataHmfDataPath": "s3://reference-data-503977275616-ap-southeast-2/refdata/hartwig/hmf-reference-data/hmftools/hmf_pipeline_resources.38_v2.1.0--1/",
    #                     "genomes": {
    #                         "GRCh38_umccr": {
    #                             "fasta": "s3://reference-data-503977275616-ap-southeast-2/refdata/genomes/GRCh38_umccr/GRCh38_full_analysis_set_plus_decoy_hla.fa",
    #                             "fai": "s3://reference-data-503977275616-ap-southeast-2/refdata/genomes/GRCh38_umccr/samtools_index/1.16/GRCh38_full_analysis_set_plus_decoy_hla.fa.fai",
    #                             "dict": "s3://reference-data-503977275616-ap-southeast-2/refdata/genomes/GRCh38_umccr/samtools_index/1.16/GRCh38_full_analysis_set_plus_decoy_hla.fa.dict",
    #                             "img": "s3://reference-data-503977275616-ap-southeast-2/refdata/genomes/GRCh38_umccr/bwa_index_image/0.7.17-r1188/GRCh38_full_analysis_set_plus_decoy_hla.fa.img",
    #                             "bwamem2Index": "s3://reference-data-503977275616-ap-southeast-2/refdata/genomes/GRCh38_umccr/bwa-mem2_index/2.2.1/",
    #                             "gridssIndex": "s3://reference-data-503977275616-ap-southeast-2/refdata/genomes/GRCh38_umccr/gridss_index/2.13.2/",
    #                             "starIndex": "s3://reference-data-503977275616-ap-southeast-2/refdata/genomes/GRCh38_umccr/star_index/gencode_38/2.7.3a/"
    #                         }
    #                     }
    #                 },
    #                 "engineParameters": {
    #                     "pipelineId": "ab6e1d62-1b5a-4b24-86b8-81ccf4bdc7a2",
    #                     "projectId": "ea19a3f5-ec7c-4940-a474-c31cd91dbad4",
    #                     "outputUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/oncoanalyser-wgts-rna/202508285cd658ee/",
    #                     "logsUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/logs/oncoanalyser-wgts-rna/202508285cd658ee/",
    #                     "cacheUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/cache/oncoanalyser-wgts-rna/202508285cd658ee/",
    #                     "analysisStorageSize": None
    #                 },
    #                 "tags": {
    #                     "libraryId": "L2500568",
    #                     "subjectId": "HCC1395",
    #                     "individualId": "SBJ00480",
    #                     "fastqRgidList": [
    #                         "GGACTTGG+CGTCTGCG.2.241024_A00130_0336_BHW7MVDSXC"
    #                     ],
    #                     "portalRunId": "202508285cd658ee"
    #                 },
    #                 "technicalTags": {
    #                     "icav2_wes_orcabus_id": "iwa.01K3QJ0RG3WME99X2DANM1VJVG",
    #                     "launch_step_functions_execution_id": "arn:aws:states:ap-southeast-2:843407916570:stateMachine:icav2-wes-launchIcav2Analysis"
    #                 }
    #             },
    #             None
    #         ),
    #         indent=4
    #     ))

    # # Oncoanalyser DNA/RNA 2.1.0 example
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
    #                 "id": "iwa.01K2AY7K7KEEQ53FZBS5TT889D",
    #                 "name": "umccr--automated--oncoanalyser-wgts-dna-rna--2-1-0--20250810758f75db",
    #                 "tags": {
    #                     "libraryId": "L2401533",
    #                     "subjectId": "Sera-ctDNA-Comp1pc",
    #                     "individualId": "SBJ05828",
    #                     "fastqRgidList": [
    #                         "CTGAAGCT+TCAGAGCC.1.241024_A00130_0336_BHW7MVDSXC"
    #                     ]
    #                 },
    #                 "technicalTags": {
    #                     "icav2_wes_orcabus_id": "iwa.01K2AY7K7KEEQ53FZBS5TT889D",
    #                     "launch_step_functions_execution_id": "arn:aws:states:ap-southeast-2:843407916570:stateMachine:icav2-wes-launchIcav2Analysis"
    #                 },
    #                 "inputs": {
    #                     "mode": "wgts",
    #                     "monochrome_logs": True,
    #                     "processes_manual": True,
    #                     "processes_include": "lilac,neo,cuppa,orange",
    #                     "samplesheet": [
    #                         {
    #                             "group_id": "SBJ05828",
    #                             "subject_id": "SBJ05828",
    #                             "sample_id": "L2401541",
    #                             "sample_type": "tumor",
    #                             "sequence_type": "dna",
    #                             "filetype": "bam_redux",
    #                             "filepath": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/oncoanalyser-wgts-dna/202508052e398fe8/SBJ05828/alignments/dna/L2401541.redux.bam"
    #                         },
    #                         {
    #                             "group_id": "SBJ05828",
    #                             "subject_id": "SBJ05828",
    #                             "sample_id": "L2401541",
    #                             "sample_type": "tumor",
    #                             "sequence_type": "dna",
    #                             "filetype": "bai",
    #                             "filepath": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/oncoanalyser-wgts-dna/202508052e398fe8/SBJ05828/alignments/dna/L2401541.redux.bam.bai"
    #                         },
    #                         {
    #                             "group_id": "SBJ05828",
    #                             "subject_id": "SBJ05828",
    #                             "sample_id": "L2401541",
    #                             "sample_type": "tumor",
    #                             "sequence_type": "dna",
    #                             "filetype": "redux_jitter_tsv",
    #                             "filepath": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/oncoanalyser-wgts-dna/202508052e398fe8/SBJ05828/alignments/dna/L2401541.jitter_params.tsv"
    #                         },
    #                         {
    #                             "group_id": "SBJ05828",
    #                             "subject_id": "SBJ05828",
    #                             "sample_id": "L2401541",
    #                             "sample_type": "tumor",
    #                             "sequence_type": "dna",
    #                             "filetype": "redux_ms_tsv",
    #                             "filepath": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/oncoanalyser-wgts-dna/202508052e398fe8/SBJ05828/alignments/dna/L2401541.ms_table.tsv.gz"
    #                         },
    #                         {
    #                             "group_id": "SBJ05828",
    #                             "subject_id": "SBJ05828",
    #                             "sample_id": "L2401540",
    #                             "sample_type": "normal",
    #                             "sequence_type": "dna",
    #                             "filetype": "bam_redux",
    #                             "filepath": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/oncoanalyser-wgts-dna/202508052e398fe8/SBJ05828/alignments/dna/L2401540.redux.bam"
    #                         },
    #                         {
    #                             "group_id": "SBJ05828",
    #                             "subject_id": "SBJ05828",
    #                             "sample_id": "L2401540",
    #                             "sample_type": "normal",
    #                             "sequence_type": "dna",
    #                             "filetype": "bai",
    #                             "filepath": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/oncoanalyser-wgts-dna/202508052e398fe8/SBJ05828/alignments/dna/L2401540.redux.bam.bai"
    #                         },
    #                         {
    #                             "group_id": "SBJ05828",
    #                             "subject_id": "SBJ05828",
    #                             "sample_id": "L2401540",
    #                             "sample_type": "normal",
    #                             "sequence_type": "dna",
    #                             "filetype": "redux_jitter_tsv",
    #                             "filepath": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/oncoanalyser-wgts-dna/202508052e398fe8/SBJ05828/alignments/dna/L2401540.jitter_params.tsv"
    #                         },
    #                         {
    #                             "group_id": "SBJ05828",
    #                             "subject_id": "SBJ05828",
    #                             "sample_id": "L2401540",
    #                             "sample_type": "normal",
    #                             "sequence_type": "dna",
    #                             "filetype": "redux_ms_tsv",
    #                             "filepath": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/oncoanalyser-wgts-dna/202508052e398fe8/SBJ05828/alignments/dna/L2401540.ms_table.tsv.gz"
    #                         },
    #                         {
    #                             "group_id": "SBJ05828",
    #                             "subject_id": "SBJ05828",
    #                             "sample_id": "L2401533",
    #                             "sample_type": "tumor",
    #                             "sequence_type": "rna",
    #                             "filetype": "bam",
    #                             "filepath": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/oncoanalyser-wgts-rna/202508093e7596dc/SBJ00595/alignments/rna/L2401533.md.bam"
    #                         },
    #                         {
    #                             "group_id": "SBJ05828",
    #                             "subject_id": "SBJ05828",
    #                             "sample_id": "L2401533",
    #                             "sample_type": "tumor",
    #                             "sequence_type": "rna",
    #                             "filetype": "bai",
    #                             "filepath": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/oncoanalyser-wgts-rna/202508093e7596dc/SBJ00595/alignments/rna/L2401533.md.bam.bai"
    #                         },
    #                         {
    #                             "group_id": "SBJ05828",
    #                             "subject_id": "SBJ05828",
    #                             "sample_id": "L2401541",
    #                             "sample_type": "tumor",
    #                             "sequence_type": "dna",
    #                             "filetype": "bamtools_dir",
    #                             "filepath": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/oncoanalyser-wgts-dna/202508052e398fe8/SBJ05828/bamtools/SBJ05828_L2401541_bamtools/"
    #                         },
    #                         {
    #                             "group_id": "SBJ05828",
    #                             "subject_id": "SBJ05828",
    #                             "sample_id": "L2401540",
    #                             "sample_type": "normal",
    #                             "sequence_type": "dna",
    #                             "filetype": "bamtools_dir",
    #                             "filepath": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/oncoanalyser-wgts-dna/202508052e398fe8/SBJ05828/bamtools/SBJ05828_L2401540_bamtools/"
    #                         },
    #                         {
    #                             "group_id": "SBJ05828",
    #                             "subject_id": "SBJ05828",
    #                             "sample_id": "L2401541",
    #                             "sample_type": "tumor",
    #                             "sequence_type": "dna",
    #                             "filetype": "sage_dir",
    #                             "filepath": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/oncoanalyser-wgts-dna/202508052e398fe8/SBJ05828/sage/somatic/"
    #                         },
    #                         {
    #                             "group_id": "SBJ05828",
    #                             "subject_id": "SBJ05828",
    #                             "sample_id": "L2401540",
    #                             "sample_type": "normal",
    #                             "sequence_type": "dna",
    #                             "filetype": "sage_dir",
    #                             "filepath": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/oncoanalyser-wgts-dna/202508052e398fe8/SBJ05828/sage/germline/"
    #                         },
    #                         {
    #                             "group_id": "SBJ05828",
    #                             "subject_id": "SBJ05828",
    #                             "sample_id": "L2401541",
    #                             "sample_type": "tumor",
    #                             "sequence_type": "dna",
    #                             "filetype": "linx_anno_dir",
    #                             "filepath": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/oncoanalyser-wgts-dna/202508052e398fe8/SBJ05828/linx/somatic_annotations/"
    #                         }, {
    #                             "group_id": "SBJ05828",
    #                             "subject_id": "SBJ05828",
    #                             "sample_id": "L2401541",
    #                             "sample_type": "tumor",
    #                             "sequence_type": "dna",
    #                             "filetype": "linx_plot_dir",
    #                             "filepath": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/oncoanalyser-wgts-dna/202508052e398fe8/SBJ05828/linx/somatic_plots/"
    #                         },
    #                         {
    #                             "group_id": "SBJ05828",
    #                             "subject_id": "SBJ05828",
    #                             "sample_id": "L2401540",
    #                             "sample_type": "normal",
    #                             "sequence_type": "dna",
    #                             "filetype": "linx_anno_dir",
    #                             "filepath": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/oncoanalyser-wgts-dna/202508052e398fe8/SBJ05828/linx/germline_annotations/"
    #                         },
    #                         {
    #                             "group_id": "SBJ05828",
    #                             "subject_id": "SBJ05828",
    #                             "sample_id": "L2401541",
    #                             "sample_type": "tumor",
    #                             "sequence_type": "dna",
    #                             "filetype": "purple_dir",
    #                             "filepath": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/oncoanalyser-wgts-dna/202508052e398fe8/SBJ05828/purple/"
    #                         },
    #                         {
    #                             "group_id": "SBJ05828",
    #                             "subject_id": "SBJ05828",
    #                             "sample_id": "L2401541",
    #                             "sample_type": "tumor",
    #                             "sequence_type": "dna",
    #                             "filetype": "virusinterpreter_dir",
    #                             "filepath": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/oncoanalyser-wgts-dna/202508052e398fe8/SBJ05828/virusinterpreter/"
    #                         },
    #                         {
    #                             "group_id": "SBJ05828",
    #                             "subject_id": "SBJ05828",
    #                             "sample_id": "L2401541",
    #                             "sample_type": "tumor",
    #                             "sequence_type": "dna",
    #                             "filetype": "chord_dir",
    #                             "filepath": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/oncoanalyser-wgts-dna/202508052e398fe8/SBJ05828/chord/"
    #                         },
    #                         {
    #                             "group_id": "SBJ05828",
    #                             "subject_id": "SBJ05828",
    #                             "sample_id": "L2401541",
    #                             "sample_type": "tumor",
    #                             "sequence_type": "dna",
    #                             "filetype": "sigs_dir",
    #                             "filepath": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/oncoanalyser-wgts-dna/202508052e398fe8/SBJ05828/sigs/"
    #                         },
    #                         {
    #                             "group_id": "SBJ05828",
    #                             "subject_id": "SBJ05828",
    #                             "sample_id": "L2401533",
    #                             "sample_type": "tumor",
    #                             "sequence_type": "rna",
    #                             "filetype": "isofox_dir",
    #                             "filepath": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/oncoanalyser-wgts-rna/202508093e7596dc/SBJ00595/isofox/"
    #                         }
    #                     ],
    #                     "genome": "GRCh38_umccr",
    #                     "genome_version": "38",
    #                     "genome_type": "alt",
    #                     "force_genome": True,
    #                     "ref_data_hmf_data_path": "s3://pipeline-prod-cache-503977275616-ap-southeast-2/byob-icav2/reference-data/hartwig/hmf-reference-data/hmftools/hmf_pipeline_resources.38_v2.1.0--1/",
    #                     "genomes": {
    #                         "GRCh38_umccr": {
    #                             "fasta": "s3://pipeline-prod-cache-503977275616-ap-southeast-2/byob-icav2/reference-data/genomes/GRCh38_umccr/GRCh38_full_analysis_set_plus_decoy_hla.fa",
    #                             "fai": "s3://pipeline-prod-cache-503977275616-ap-southeast-2/byob-icav2/reference-data/genomes/GRCh38_umccr/samtools_index/1.16/GRCh38_full_analysis_set_plus_decoy_hla.fa.fai",
    #                             "dict": "s3://pipeline-prod-cache-503977275616-ap-southeast-2/byob-icav2/reference-data/genomes/GRCh38_umccr/samtools_index/1.16/GRCh38_full_analysis_set_plus_decoy_hla.fa.dict",
    #                             "img": "s3://pipeline-prod-cache-503977275616-ap-southeast-2/byob-icav2/reference-data/genomes/GRCh38_umccr/bwa_index_image/0.7.17-r1188/GRCh38_full_analysis_set_plus_decoy_hla.fa.img",
    #                             "bwamem2_index": "s3://pipeline-prod-cache-503977275616-ap-southeast-2/byob-icav2/reference-data/genomes/GRCh38_umccr/bwa-mem2_index/2.2.1/",
    #                             "gridss_index": "s3://pipeline-prod-cache-503977275616-ap-southeast-2/byob-icav2/reference-data/genomes/GRCh38_umccr/gridss_index/2.13.2/",
    #                             "star_index": "s3://pipeline-prod-cache-503977275616-ap-southeast-2/byob-icav2/reference-data/genomes/GRCh38_umccr/star_index/gencode_38/2.7.3a/"
    #                         }
    #                     }
    #                 },
    #                 "engineParameters": {
    #                     "logsUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/logs/oncoanalyser-wgts-dna-rna/20250810758f75db/",
    #                     "cacheUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/cache/oncoanalyser-wgts-dna-rna/20250810758f75db/",
    #                     "outputUri": "s3://pipeline-dev-cache-503977275616-ap-southeast-2/byob-icav2/development/analysis/oncoanalyser-wgts-dna-rna/20250810758f75db/",
    #                     "projectId": "ea19a3f5-ec7c-4940-a474-c31cd91dbad4",
    #                     "pipelineId": "ab6e1d62-1b5a-4b24-86b8-81ccf4bdc7a2"
    #                 }
    #             },
    #             None
    #         ),
    #         indent=4
    #     ))
