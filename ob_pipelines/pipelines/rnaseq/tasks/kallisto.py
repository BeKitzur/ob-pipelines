from os import path as op

from luigi.contrib.s3 import S3Target

from ob_pipelines.batch import BatchTask, LoggingTaskWrapper
from ob_pipelines.config import cfg
from ob_pipelines.entities.sample import Sample
from ob_pipelines.pipelines.rnaseq.index import get_index
from ob_pipelines.tasks.sample_fastq import SampleFastQ


class Kallisto(BatchTask, LoggingTaskWrapper, Sample):
    job_definition = 'kallisto'

    @property
    def parameters(self):
        fq1, fq2 = self.input()
        return {
            'threads': '20',
            'index': get_index('kallisto'),
            'reads1': fq1.path,
            'reads2': fq2.path,
            'strand_flag': '--rf-stranded',
            'output': op.dirname(self.output()['abundance'].path) + '/'
        }

    def requires(self):
        return SampleFastQ(sample_id=self.sample_id)

    def output(self):
        output_files = {
            'abundance': 'abundance.tsv',
            'h5': 'abundance.h5',
            'run_info': 'run_info.json'
        }
        return {k: S3Target('{}/{}/kallisto/{}'.format(cfg['S3_BUCKET'], self.sample_folder, fname))
                for k, fname in output_files.items()}
