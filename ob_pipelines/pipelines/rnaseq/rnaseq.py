import logging

from luigi import Parameter, WrapperTask

from ob_pipelines.entities.persistence import get_samples_by_experiment_id
from ob_pipelines.pipelines.rnaseq.tasks.kallisto import Kallisto
from ob_pipelines.pipelines.rnaseq.tasks.kallisto_spliced import KallistoSpliced
from ob_pipelines.pipelines.rnaseq.tasks.star import Star
from ob_pipelines.tasks.fastqc import FastQC
from ob_pipelines.tasks.gene_coverage import GeneCoverage
from ob_pipelines.tasks.index_bam import IndexBam
from ob_pipelines.tasks.merge_ercc import MergeERCC
from ob_pipelines.tasks.merge_kallisto import MergeKallisto
from ob_pipelines.tasks.read_distribution import ReadDistribution

logger = logging.getLogger('luigi-interface')


def get_index(tool, species='human', build='latest'):
    indexes = {
        'star': {
            'human': {
                'test': '/reference/star/b38.chr21.gencode_v25.101',
                'latest': '/reference/star/b38.gencode_v25.101'
            },
            'mouse': {
                'latest': '/reference/star/m38.gencode_vM12.101'
            }
        },
        'kallisto': {
            'human': {
                'test': '/reference/kallisto/gencode_v25.chr21/gencode_v25.chr21.idx',
                'latest': '/reference/kallisto/gencode_v25/gencode.v25.ercc.idx'
            }
        }
    }
    return indexes[tool][species][build]


class RnaSeq(WrapperTask):
    expt_id = Parameter()

    def requires(self):
        for sample_id in get_samples_by_experiment_id(self.expt_id):
            yield FastQC(sample_id=sample_id)
            yield Star(sample_id=sample_id)
            yield IndexBam(sample_id=sample_id)
            yield Kallisto(sample_id=sample_id)
            yield GeneCoverage(sample_id=sample_id)
            yield ReadDistribution(sample_id=sample_id)
            yield KallistoSpliced(sample_id=sample_id)
        yield MergeKallisto(expt_id=self.expt_id)
        yield MergeERCC(expt_id=self.expt_id)