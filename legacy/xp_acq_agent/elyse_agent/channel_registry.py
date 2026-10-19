from __future__ import print_function

import csv
import os


class ChannelRegistry(object):
    FILENAMES = ("channel_map.csv", "calibration_map.csv", "ni6602_timing.csv")

    def __init__(self, data_path):
        self.data_path = os.path.abspath(data_path)
        self.tables = {}

    def load(self):
        tables = {}
        for filename in self.FILENAMES:
            path = os.path.join(self.data_path, filename)
            with open(path, "r") as stream:
                rows = list(csv.DictReader(stream))
            tables[filename] = rows
        self.tables = tables
        return self

    def summary(self):
        return dict((name, len(rows)) for name, rows in sorted(self.tables.items()))

    def get_rows(self, filename):
        return list(self.tables[filename])
