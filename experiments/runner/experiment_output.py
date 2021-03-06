import csv
import logging
import sys
import traceback
from cProfile import Profile
from os import path, listdir, makedirs
from typing import List, Any, Dict, Tuple
from typing import Union

from experiments.enum.implementations import implementations
from experiments.runner.experiment_state import ExperimentState
from shared.connection.base_connection import BaseConnection
from shared.utils.measure_util import connections_to_csv, pstats_to_step_timings

OUTPUT_DIRECTORY = 'results'

OUTPUT_DETAILED = False


class ExperimentOutput(object):
    """
    Utility class for exporting experiment results.
    """

    def __init__(self, experiment_name: str, state: ExperimentState) -> None:
        if not path.exists(OUTPUT_DIRECTORY):
            makedirs(OUTPUT_DIRECTORY)
        self.experiment_name = experiment_name
        self.state = state

    def experiment_results_directory(self) -> str:
        """
        Gets the base directory for the results of the experiment
        """
        return path.join(OUTPUT_DIRECTORY,
                         self.experiment_name,
                         self.state.device_name,
                         self.state.timestamp
                         )

    def experiment_case_iteration_results_directory(self) -> str:
        """
        Gets the base directory for the results of the experiment for the current case and implementation.
        :require: experiments_run.implementation is not None and experiments_run.case is not None
        """
        return path.join(
            self.experiment_results_directory(),
            self.state.implementation.get_name(),
            self.state.case.name,
            str(self.state.iteration)
        )

    def output_cpu_usage(self, cpu_usage: float) -> None:
        """
        Output the cpu usage of the previous experiment.
        :param cpu_usage: The measured cpu usage
        """
        # if OUTPUT_DETAILED:
        #     directory = ExperimentOutput.experiment_case_iteration_results_directory(experiments_state)
        #     with open(path.join(directory, 'cpu.txt'), 'w') as file:
        #         file.write(str(cpu_usage))

        output_file_path = path.join(self.experiment_results_directory(), 'cpu.csv')
        headers = ['case'] + list(map(lambda i: i.get_name(), implementations))  # type: ignore
        implementation_index = self.determine_implementation_index()

        ExperimentOutput.append_row_to_file(
            output_file_path,
            headers,
            ExperimentOutput.create_row(self.state.case.name, cpu_usage, implementation_index)
        )

    @staticmethod
    def output_error() -> None:
        """
        Output an error. The last exception is printed.
        """
        logging.error(traceback.format_exc())
        traceback.print_exc(file=sys.stderr)

    def output_connections(self, connections: List[BaseConnection]) -> None:
        """
        Output the network usage.
        :param connections: The connections to output the usage of.
        """
        if OUTPUT_DETAILED:
            directory = self.experiment_case_iteration_results_directory()
            connections_to_csv(connections, path.join(directory, 'network.csv'))

        values = list()
        for connection in connections:
            for (name, sizes) in connection.benchmarks.items():
                for size in sizes:
                    values.append((name, size))

        self.output_case_results('network', values)

    def output_cpu_times(self, cpu_times: List[Tuple[str, float]]):
        self.output_case_results('cpu', cpu_times)

    def output_storage_space(self, directories: List[dict]) -> None:
        """
        Output the storage space used by the different parties.
        :param directories: A list of directory options. Each directory option contains at least a 'path' value.
        An 'filename_mapper' value is optional.
        """
        values = list()

        for directory_options in directories:
            directory_path = directory_options['path']
            filename_mapper = directory_options['filename_mapper'] \
                if 'filename_mapper' in directory_options \
                else lambda x: x

            for file in listdir(directory_path):
                size = path.getsize(path.join(directory_path, file))
                values.append((filename_mapper(file), size))

        self.output_case_results('storage', values)

    def output_timings(self, profile: Profile) -> None:
        """
        Output the timings measured by the profiler.
        :param profile: The profile.
        """
        directory = self.experiment_results_directory()
        stats_file_path = path.join(directory, 'timings.pstats')

        # Write raw stats
        profile.dump_stats(stats_file_path)

        # Process raw stats
        step_timings = pstats_to_step_timings(stats_file_path)

        self.output_case_results('timings', step_timings)

    def output_case_results(self,
                            name: str,
                            values: List[Tuple[str, Any]],
                            skip_categories=False,
                            variables: List[str] = None
                            ) -> None:
        """
        Output the results of a single case to the different files (one file for the current case, one file
        for each category)
        :param name: The name of the measurement (for example 'network' or 'memory')
        :param values: A list containing tuples containing category and (list of) value.
        A category is for example a step in the algorithm ('encrypt', 'decrypt'), or filename for storage.
        :param skip_categories: If true, skip appending to the category specific files
        :param variables: A list of variables. By default, only one value per implementation is used. Using this list,
        multiple variables can be exported per implementation (for example min and max values).
        """

        implementation_index = self.determine_implementation_index()
        variables_amount = len(variables) if variables is not None else 1
        headers = ['case/step']
        for implementation in implementations:
            if variables is not None:
                # noinspection PyTypeChecker
                for variable in variables:
                    headers.append("%s %s" % (implementation.get_name(), variable))
            else:
                headers.append(implementation.get_name())

        case_output_file_path = path.join(self.experiment_results_directory(),
                                          '%s-case-%s.csv' % (name, self.state.case.name))

        case_rows = list()
        for category, value in values:
            case_rows.append(ExperimentOutput.create_row(category, value, implementation_index, variables_amount))

            if not skip_categories:
                category_row = ExperimentOutput.create_row(self.state.case.name, value,
                                                           implementation_index, variables_amount)
                category_output_file_path = path.join(
                    self.experiment_results_directory(),
                    '%s-category-%s.csv' % (name, category))
                ExperimentOutput.append_row_to_file(
                    category_output_file_path,
                    headers,
                    category_row
                )

        ExperimentOutput.append_rows_to_file(
            case_output_file_path,
            headers,
            case_rows
        )

    @staticmethod
    def create_row(category: str, value: Union[List[float], float], implementation_index: int,
                   variables_amount: int = 1):
        row = [None] * (1 + 4 * variables_amount)  # type: List[Union[str, Any]]
        row[0] = category
        if variables_amount == 1:
            row[implementation_index + 1] = value
        else:
            for i in range(variables_amount):
                row[implementation_index * variables_amount + i + 1] = value[i]  # type: ignore

        return row

    def determine_implementation_index(self):
        return implementations.index(self.state.implementation)

    @staticmethod
    def append_rows_to_file(file_path, headers, rows):
        write_header = not path.exists(file_path)
        with open(file_path, 'a') as file:
            writer = csv.writer(file)
            if write_header:
                writer.writerow(headers)
            for row in rows:
                writer.writerow(row)

    @staticmethod
    def append_row_to_file(file_path, headers, row):
        write_header = not path.exists(file_path)
        with open(file_path, 'a') as file:
            writer = csv.writer(file)
            if write_header:
                writer.writerow(headers)
            writer.writerow(row)

    @staticmethod
    def append_dict_to_file(file_path, headers, row: Dict[str, Any]):
        write_header = not path.exists(file_path)
        with open(file_path, 'a') as file:
            writer = csv.DictWriter(file, headers)
            if write_header:
                writer.writeheader()
            writer.writerow(row)
