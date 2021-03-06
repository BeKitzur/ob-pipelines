from luigi.contrib.s3 import S3Target

from ob_pipelines.batch import BatchTask, LoggingTaskWrapper
from ob_pipelines.config import cfg
from ob_pipelines.entities.sample import Sample
from ob_pipelines.tasks.index_bam import IndexBam
from ob_pipelines.tasks.sort_bam import SortBam


class FilterSpliced(BatchTask, LoggingTaskWrapper, Sample):
    job_definition = 'filter-spliced'

    @property
    def parameters(self):
        return {
            'input': self.input()[0].path,
            'output': self.output().path
        }

    def requires(self):
        return SortBam(sample_id=self.sample_id), IndexBam(sample_id=self.sample_id)

    def output(self):
        return S3Target('{}/{}/filtered/{}.spliced_reads.bam'.format(
            cfg['S3_BUCKET'], self.sample_folder, self.sample_id))
