"""Coverage data for Coverage."""

import os

from coverage.backward import pickle, sorted    # pylint: disable-msg=W0622


class CoverageData:
    """Manages collected coverage data, including file storage.
    
    The data file format is a pickled dict, with these keys:
    
        * collector: a string identifying the collecting software

        * lines: a dict mapping filenames to sorted lists of line numbers
          executed:
            { 'file1': [17,23,45],  'file2': [1,2,3], ... }
    
        * arcs: a dict mapping filenames to sorted lists of line number pairs:
            { 'file1': [(17,23), (17,25), (25,26)], ... }

    """
    
    # Name of the data file (unless environment variable is set).
    filename_default = ".coverage"

    # Environment variable naming the data file.
    filename_env = "COVERAGE_FILE"

    def __init__(self, basename=None, suffix=None, collector=None):
        """Create a CoverageData.
        
        `basename` is the name of the file to use for storing data.
        
        `suffix` is a suffix to append to the base file name. This can be used
        for multiple or parallel execution, so that many coverage data files
        can exist simultaneously.

        `collector` is a string describing the coverage measurement software.

        """
        self.collector = collector
        
        self.use_file = True

        # Construct the filename that will be used for data file storage, if we
        # ever do any file storage.
        self.filename = (basename or
                os.environ.get(self.filename_env, self.filename_default))
        if suffix:
            self.filename += suffix
        self.filename = os.path.abspath(self.filename)

        # A map from canonical Python source file name to a dictionary in
        # which there's an entry for each line number that has been
        # executed:
        #
        #   {
        #       'filename1.py': { 12: None, 47: None, ... },
        #       ...
        #       }
        #
        self.lines = {}
        
        self.arcs = {}  # TODO
        
    def usefile(self, use_file=True):
        """Set whether or not to use a disk file for data."""
        self.use_file = use_file

    def read(self):
        """Read coverage data from the coverage data file (if it exists)."""
        if self.use_file:
            self.lines, self.arcs = self._read_file(self.filename)
        else:
            self.lines, self.arcs = {}, {}

    def write(self):
        """Write the collected coverage data to a file."""
        if self.use_file:
            self.write_file(self.filename)

    def erase(self):
        """Erase the data, both in this object, and from its file storage."""
        if self.use_file:
            if self.filename and os.path.exists(self.filename):
                os.remove(self.filename)
        self.lines = {}
        self.arcs = {}
        
    def line_data(self):
        """Return the map from filenames to lists of line numbers executed."""
        return dict(
            [(f, sorted(lmap.keys())) for f, lmap in self.lines.items()]
            )

    def arc_data(self):
        """Return the map from filenames to lists of line number pairs."""
        return dict(
            [(f, sorted(amap.keys())) for f, amap in self.arcs.items()]
            )
        
    def write_file(self, filename):
        """Write the coverage data to `filename`."""

        # Create the file data.        
        data = {}

        data['lines'] = self.line_data()
        arcs = self.arc_data()
        if arcs:
            data['arcs'] = arcs

        if self.collector:
            data['collector'] = self.collector

        # Write the pickle to the file.
        fdata = open(filename, 'wb')
        try:
            pickle.dump(data, fdata, 2)
        finally:
            fdata.close()

    def read_file(self, filename):
        """Read the coverage data from `filename`."""
        self.lines, self.arcs = self._read_file(filename)

    def raw_data(self, filename):
        """Return the raw pickled data from `filename`."""
        fdata = open(filename, 'rb')
        try:
            data = pickle.load(fdata)
        finally:
            fdata.close()
        return data

    def _read_file(self, filename):
        """Return the stored coverage data from the given file."""
        lines = {}
        arcs = {}
        try:
            data = self.raw_data(filename)
            if isinstance(data, dict):
                # Unpack the 'lines' item.
                lines = dict([
                    (f, dict.fromkeys(linenos, None))
                        for f, linenos in data.get('lines', {}).items()
                    ])
                # Unpack the 'arcs' item.
                arcs = dict([
                    (f, dict.fromkeys(arcpairs, None))
                        for f, arcpairs in data.get('arcs', {}).items()
                    ])
        except Exception:
            pass
        return lines, arcs

    def combine_parallel_data(self):
        """ Treat self.filename as a file prefix, and combine the data from all
            of the files starting with that prefix.
        """
        data_dir, local = os.path.split(self.filename)
        for f in os.listdir(data_dir or '.'):
            if f.startswith(local):
                full_path = os.path.join(data_dir, f)
                new_lines, new_arcs = self._read_file(full_path)
                for filename, file_data in new_lines.items():
                    self.lines.setdefault(filename, {}).update(file_data)

    def add_line_data(self, line_data):
        """Add executed line data.
        
        `line_data` is { filename: { lineno: None, ... }, ...}
        
        """
        for filename, linenos in line_data.items():
            self.lines.setdefault(filename, {}).update(linenos)

    def add_arc_data(self, arc_data):
        """Add measured arc data.
        
        `arc_data` is { filename: { (l1,l2): None, ... }, ...}
        
        """
        for filename, arcs in arc_data.items():
            self.arcs.setdefault(filename, {}).update(arcs)

    def executed_files(self):
        """A list of all files that had been measured as executed."""
        return list(self.lines.keys())

    def executed_lines(self, filename):
        """A map containing all the line numbers executed in `filename`.
        
        If `filename` hasn't been collected at all (because it wasn't executed)
        then return an empty map.

        """
        return self.lines.get(filename) or {}

    def executed_arcs(self, filename):
        """A map containing all the arcs executed in `filename`."""
        return self.arcs.get(filename) or {}

    def summary(self, fullpath=False):
        """Return a dict summarizing the coverage data.
        
        Keys are based on the filenames, and values are the number of executed
        lines.  If `fullpath` is true, then the keys are the full pathnames of
        the files, otherwise they are the basenames of the files.
        
        """
        summ = {}
        if fullpath:
            filename_fn = lambda f: f
        else:
            filename_fn = os.path.basename
        for filename, lines in self.lines.items():
            summ[filename_fn(filename)] = len(lines)
        return summ

if __name__ == '__main__':
    # Ad-hoc: show the raw data in a data file.
    import pprint, sys
    covdata = CoverageData()
    if sys.argv[1:]:
        fname = sys.argv[1]
    else:
        fname = covdata.filename
    pprint.pprint(covdata.raw_data(fname))
