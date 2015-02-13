import importlib
from abc import abstractmethod, ABCMeta
import numpy as np


try:
    import pyproj  # Import pyproj
except:
    try:
        # ...alternatively use version included with Basemap
        from mpl_toolkits.basemap import pyproj
    except:
        raise ImportError('pyproj needed for coordinate transformations,'
                          ' please install from '
                          'https://code.google.com/p/pyproj/')


class Reader(object):
    """Parent Reader class, to be subclassed by specific readers.
    """

    __metaclass__ = ABCMeta

    def __init__(self):
        # Common constructor for all readers

        # Set projection for coordinate transformations
        self.proj = pyproj.Proj(self.proj4)

    @abstractmethod
    def get_variables(self, variables, time=None,
                      x=None, y=None, depth=None, block=False):
        """Method which must be invoked by any reader (subclass).

        Obtain and return values of the requested variables at all positions
        (x, y, depth) closest to given time.
        
        Arguments:
            variables: string, or list of strings (standard_name) of
                requested variables. These must be provided by reader.
            time: datetime or None, time at which data are requested.
                Can be None (default) if reader/variable has no time 
                dimension (e.g. climatology or landmask).
            x, y: float or ndarrays; coordinates of requested points in the
                Spatial Reference System (SRS) of the reader (NB!!)
            depth: float or ndarray; depth (in meters) of requested points.
                default: 0 m (unless otherwise documented by reader)
            block: bool, see return below

          Returns:
            data: Dictionary
                keywords: variables (string)
                values:
                    - 1D ndarray of len(x) if block=False. Nearest values
                        (neichbour) of requested position are returned.
                    - 3D ndarray encompassing all requested points in
                        x,y,depth domain if block=True. It is task of invoking
                        application (OpenDriftSimulation) to perform 
                        interpolation in space and time.
        """

    def xy2lonlat(self, x, y):
        """Calculate x,y in own projection from given lon,lat (scalars/arrays).
        """
        return self.proj(x, y, inverse=True)

    def lonlat2xy(self, lon, lat):
        """Calculate lon,lat from given x,y (scalars/arrays) in own projection.
        """
        return self.proj(lon, lat, inverse=False)

    def check_arguments(self, variables, time, x, y, depth):
        """Check validity of arguments input to method get_variables.
        
        Checks that requested positions and time are within coverage of
        this reader, and that it can provide the requested variable(s).
        Returns the input arguments, possibly modified/corrected (below)

        Arguments:
            See function get_variables for definition.

        Returns:
            variables: same as input, but converted to list if given as string.
            time: same as input, or startTime of reader if given as None.
            x, y, depth: same as input, but converted to ndarrays
                if given as scalars.
            outside: boolean array which is True for any particles outside
                the spatial domain covered by this reader.

        Raises:
            ValueError:
                - if requested time is outside coverage of reader.
                - if all requested positions are outside coverage of reader.
        """

        # Check time
        if time is None:
            time = self.startTime  # Get data from first timestep, if not given
            indxTime = 0

        # Convert variables to list and x,y to ndarrays
        if isinstance(variables, str):
            variables = [variables]
        x = np.asarray(x)
        y = np.asarray(y)
        depth = np.asarray(depth)

        for variable in variables:
            if variable not in self.variables:
                raise ValueError('Variable not available: ' + variable +
                                 '\nAvailable parameters are: ' +
                                 str(self.variables))
        if self.startTime is not None and time < self.startTime:
            raise ValueError('Requested time (%s) is before first available '
                             'time (%s)' % (time, self.startTime))
        if self.endTime is not None and time > self.endTime:
            raise ValueError('Requested time (%s) is after last available '
                             'time (%s)' % (time, self.endTime))
        outside = np.where((x < self.xmin) | (x > self.xmax) |
                           (y < self.xmin) | (y > self.ymax))[0]
        if len(outside) == len(x):
            raise ValueError('All particles are outside domain '
                             'of reader ' + self.name)

        return variables, time, x, y, depth, outside

    def index_of_closest_time(self, requestedTime):
        """Return (internal) index of internal time closest to requested time.

        Assuming time step is constant; this method should be
        overloaded for readers for which this is not the case
        """
        indx = float((requestedTime - self.startTime).total_seconds()) / \
            float(self.timeStep.total_seconds())
        indx = int(round(indx))
        nearestTime = self.times[indx]
        return indx, nearestTime

    def indices_min_max_depth(self, depths):
        """
        Return min and max indices of internal depth dimension,
        covering the requested depths. Needed when block is requested (True).

        Arguments:
            depths: ndarray of floats, in meters
        """
        minIndex = (self.depths <= depths.min()).argmin() - 1
        maxIndex = (self.depths >= depths.max()).argmax()
        return minIndex, maxIndex

    def __repr__(self):
        """String representation of the current reader."""
        outStr = '===========================\n'
        outStr += 'Reader: ' + self.name + '\n'
        outStr += 'Projection: \n  ' + self.proj4 + '\n'
        outStr += 'Coverage: \n'
        outStr += '  xmin: %f   xmax: %f   step: %f\n' % \
            (self.xmin, self.xmax, self.delta_x or 0)
        outStr += '  ymin: %f   ymax: %f   step: %f\n' % \
            (self.ymin, self.ymax, self.delta_y or 0)
        corners = self.xy2lonlat([self.xmin, self.xmin, self.xmax, self.xmax],
                                 [self.ymax, self.ymin, self.ymax, self.ymin])
        outStr += '  Corners (lon, lat):\n'
        outStr += '    (%6.2f, %6.2f)  (%6.2f, %6.2f)\n' % \
            (corners[0][0],
             corners[1][0],
             corners[0][2],
             corners[1][2])
        outStr += '    (%6.2f, %6.2f)  (%6.2f, %6.2f)\n' % \
            (corners[0][1],
             corners[1][1],
             corners[0][3],
             corners[1][3])
        if hasattr(self, 'depth'):
            outStr += 'Depths [m]: \n  ' + str(self.depths) + '\n'
        outStr += 'Available time range:\n'
        outStr += '  start: ' + str(self.startTime) + \
                  '   end: ' + str(self.endTime) + \
                  '   step: ' + str(self.timeStep) + '\n'
        outStr += 'Variables:\n'
        for variable in self.variables:
            outStr += '  ' + variable + '\n'
        outStr += '===========================\n'
        return outStr
