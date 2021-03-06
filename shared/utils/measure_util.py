import csv
import marshal
import os
from typing import Dict, List, Tuple

from shared.connection.base_connection import BaseConnection


def pstats_to_csv(input_file_path: str, output_file_path: str, filtered_functions: List[str] = None):
    with open(input_file_path, 'rb') as input_file:
        with open(output_file_path, 'w') as output_file:
            stats = marshal.load(input_file)  # type: Dict
            # The output dictionary maps a tuple describing a function (filename, line number, name)
            # to a tuple of statistics.
            # The tuple's data is (number of calls, number of non-recursive calls, total time,
            # cumulative time, subcall statistics).
            headers = ['path', 'filename', 'line number', 'name', 'number of calls', 'number or non-recursive calls',
                       'total time', 'cumtime']
            writer = csv.writer(output_file)
            writer.writerow(headers)
            for (function, statistics) in stats.items():
                if filtered_functions is None or function[2] in filtered_functions:
                    writer.writerow(
                        [list(function)[0], strip_directories(list(function)[0])] + list(function)[1:3] + list(
                            statistics)[0:4])


def pstats_to_csv_filtered(input_file_path: str, output_file_path: str):
    return pstats_to_csv(input_file_path, output_file_path, timing_functions)


def strip_directories(path: str) -> str:
    return os.path.basename(path)


function_step_mapping = {
    '_run_authsetup': 'authsetup',
    '_run_setup': 'setup',
    '_run_keygen': 'keygen',
    '_run_register': 'register',
    '_run_encrypt': 'encrypt',
    '_run_decrypt': 'decrypt',
    '_run_data_update': 'data_update',
    '_run_policy_update': 'policy_update',
    '_run_update_keys': 'update_keys'
}
timing_functions = list(function_step_mapping.keys())
algorithm_steps = set(list(function_step_mapping.values()))


def pstats_to_step_timings(input_file_path: str) -> List[Tuple[str, float]]:
    with open(input_file_path, 'rb') as input_file:
        stats = marshal.load(input_file)
        timings = []  # type: List[Tuple[str, float]]

        # The output dictionary maps a tuple describing a function (filename, line number, name)
        # to a tuple of statistics. The tuple's data is (number of calls,
        # number of non-recursive calls, total time, cumulative time, subcall statistics).
        # You can easily take this dictionary and do further processing.
        # Source: https://zameermanji.com/blog/2012/6/30/undocumented-cprofile-features/
        for (function, statistics) in stats.items():
            path = list(function)[0]
            # Do not include lib functions
            if 'abe-healthcare' in path and function[2] in function_step_mapping:
                step = function_step_mapping[function[2]]
                # We take the cumulative time divided by the number of calls
                value = statistics[3] / statistics[0]
                timings.append((step, value))

        return timings


def connections_to_csv(connections: List[BaseConnection], output_file_path: str) -> None:
    with open(output_file_path, 'w') as output_file:
        headers = ['connection', 'name', 'size']
        writer = csv.writer(output_file)
        writer.writerow(headers)
        for connection in connections:
            for (name, sizes) in connection.benchmarks.items():
                for size in sizes:
                    writer.writerow((connection.__class__.__name__, name, size))
