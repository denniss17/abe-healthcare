from os.path import join
from typing import List

from experiments.base_experiment import BaseExperiment
from experiments.experiment_case import ExperimentCase
from shared.utils.random_file_generator import RandomFileGenerator


class FileSizeExperiment(BaseExperiment):
    run_descriptions = {
        'setup_authsetup': 'once',
        'register_keygen': 'once'
    }

    def __init__(self, cases: List[ExperimentCase] = None) -> None:
        if cases is None:
            cases = list(map(lambda size: ExperimentCase(size, {'file_size': size}),
                             [
                                 1,
                                 2 ** 10,
                                 2 ** 20,
                                 10 * (2 ** 20),
                                 50 * (2 ** 20),
                                 2 ** 30
                             ]))
        super().__init__(cases)

    def global_setup(self) -> None:
        """
        Setup all implementation and case independent things for this experiment, like generating random input files.
        This method is only called once for each experiment, namely at the very start.
        """
        file_generator = RandomFileGenerator()
        input_path = self.get_experiment_input_path()
        for case in self.cases:
            file_generator.generate(case.arguments['file_size'], 1, input_path, skip_if_exists=True, verbose=True)

    def setup(self):
        super().setup()
        input_path = self.get_experiment_input_path()
        self.file_name = join(input_path, '%i-0' % self.state.case.arguments['file_size'])
