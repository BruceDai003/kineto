# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# --------------------------------------------------------------------------
import sys

from .. import consts, io, utils
from ..run import Run
from .data import RunData, RunProfileData
from .run_generator import RunGenerator, AllRunGenerator

logger = utils.get_logger()


class RunLoader(object):
    def __init__(self, name, run_dir, caches):
        self.run = RunData(name, run_dir)
        self.caches = caches

    def load(self):
        self._parse()
        if len(self.run.profiles) == 0:
            logger.warning("No profile data found.")
            return None

        self._process()

        self._analyze()

        run = self._generate_run()
        return run

    def _parse(self):
        workers = []
        for path in io.listdir(self.run.run_dir):
            if io.isdir(io.join(self.run.run_dir, path)):
                continue
            match = consts.WORKER_PATTERN.match(path)
            if not match:
                continue

            worker = match.group(1)
            workers.append((worker, path))

        for worker, path in sorted(workers):
            try:
                data = RunProfileData.parse(self.run.run_dir, worker, path, self.caches)
                self.run.profiles[worker] = data
            except Exception as ex:
                logger.warning("Failed to parse profile data for Run %s on %s. Exception=%s",
                               self.run.name, worker, ex, exc_info=True)

    def _process(self):
        comm_node_lists = []
        for data in self.run.profiles.values():
            logger.debug("Processing profile data")
            data.process()
            comm_node_lists.append(data.comm_node_list)
            logger.debug("Processing profile data finish")

        worker_num = len(comm_node_lists)
        for i in range(len(comm_node_lists[0])):
            for j in range(len(comm_node_lists[0][i].kernel_ranges)):
                min_range = sys.maxsize
                for k in range(worker_num):
                    if comm_node_lists[k][i].kernel_ranges[j][1] - comm_node_lists[k][i].kernel_ranges[j][0] < min_range:
                        min_range = comm_node_lists[k][i].kernel_ranges[j][1] - comm_node_lists[k][i].kernel_ranges[j][0]
                for k in range(worker_num):
                    comm_node_lists[k][i].real_time += min_range

        for data in self.run.profiles.values():
            data.communication_parse()


    def _analyze(self):
        for data in self.run.profiles.values():
            logger.debug("Analyzing profile data")
            data.analyze()
            logger.debug("Analyzing profile data finish")

    def _generate_run(self):
        run = Run(self.run.name, self.run.run_dir)
        has_communication = False
        for worker, data in self.run.profiles.items():
            generator = RunGenerator(worker, data)
            profile = generator.generate_run_profile()
            run.add_profile(profile)
            if profile.has_communication:
                has_communication = True
        if has_communication:
            generator = AllRunGenerator(self.run.profiles)
            all_profile = generator.generate_all_run_profile()
            run.add_profile(all_profile)
        return run
