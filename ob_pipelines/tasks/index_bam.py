from luigi.contrib.s3 import S3Target

from ob_pipelines.batch import BatchTask
from ob_pipelines.entities.sample import Sample
from ob_pipelines.tasks.sort_bam import SortBam


class IndexBam(BatchTask, Sample):
    job_definition = 'samtools-index'
    image = 'outlierbio/samtools'
    command = ['index', 'Ref::input', 'Ref::output']

    @property
    def parameters(self):
        return {
            'input': self.input().path,
            'output': self.output().path
        }

    def requires(self):
        return SortBam(sample_id=self.sample_id)

    def output(self):
        return S3Target(self.input().path + '.bai')