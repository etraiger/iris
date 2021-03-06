# (C) British Crown Copyright 2013 - 2015, Met Office
#
# This file is part of Iris.
#
# Iris is free software: you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the
# Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Iris is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Iris.  If not, see <http://www.gnu.org/licenses/>.
"""
Unit tests for the `iris.fileformats.pp._data_bytes_to_shaped_array` function.

"""

from __future__ import (absolute_import, division, print_function)
from six.moves import (filter, input, map, range, zip)  # noqa

# Import iris.tests first so that some things can be initialised before
# importing anything else.
import iris.tests as tests

import io

import numpy as np

import iris.fileformats.pp as pp
from iris.tests import mock


class Test__data_bytes_to_shaped_array__lateral_boundary_compression(
        tests.IrisTest):
    def setUp(self):
        self.data_shape = 30, 40
        y_halo, x_halo, rim = 2, 3, 4

        data_len = np.prod(self.data_shape)
        decompressed = np.arange(data_len).reshape(*self.data_shape)
        decompressed *= np.arange(self.data_shape[1]) % 3 + 1

        decompressed_mask = np.zeros(self.data_shape, np.bool)
        decompressed_mask[y_halo+rim:-(y_halo+rim),
                          x_halo+rim:-(x_halo+rim)] = True

        self.decompressed = np.ma.masked_array(decompressed,
                                               mask=decompressed_mask)

        self.north = decompressed[-(y_halo+rim):, :]
        self.east = decompressed[y_halo+rim:-(y_halo+rim), -(x_halo+rim):]
        self.south = decompressed[:y_halo+rim, :]
        self.west = decompressed[y_halo+rim:-(y_halo+rim), :x_halo+rim]

        # Get the bytes of the north, east, south, west arrays combined.
        buf = io.BytesIO()
        buf.write(self.north.copy())
        buf.write(self.east.copy())
        buf.write(self.south.copy())
        buf.write(self.west.copy())
        buf.seek(0)
        self.data_payload_bytes = buf.read()

    def test_boundary_decompression(self):
        boundary_packing = mock.Mock(rim_width=4, x_halo=3, y_halo=2)
        lbpack = mock.Mock(n1=0)
        r = pp._data_bytes_to_shaped_array(self.data_payload_bytes,
                                           lbpack, boundary_packing,
                                           self.data_shape,
                                           self.decompressed.dtype, -99)
        self.assertMaskedArrayEqual(r, self.decompressed)


class Test__data_bytes_to_shaped_array__land_packed(tests.IrisTest):
    def setUp(self):
        # Sets up some useful arrays for use with the land/sea mask
        # decompression.
        self.land = np.array([[0, 1, 0, 0],
                              [1, 0, 0, 0],
                              [0, 0, 0, 1]], dtype=np.float64)
        sea = ~self.land.astype(np.bool)
        self.land_masked_data = np.array([1, 3, 4.5])
        self.sea_masked_data = np.array([1, 3, 4.5, -4, 5, 0, 1, 2, 3])

        # Compute the decompressed land mask data.
        self.decomp_land_data = np.ma.masked_array([[0, 1, 0, 0],
                                                    [3, 0, 0, 0],
                                                    [0, 0, 0, 4.5]],
                                                   mask=sea,
                                                   dtype=np.float64)
        # Compute the decompressed sea mask data.
        self.decomp_sea_data = np.ma.masked_array([[1, -10, 3, 4.5],
                                                   [-10, -4, 5, 0],
                                                   [1, 2, 3, -10]],
                                                  mask=self.land,
                                                  dtype=np.float64)

        self.land_mask = mock.Mock(data=self.land,
                                   lbrow=self.land.shape[0],
                                   lbnpt=self.land.shape[1])

    def create_lbpack(self, value):
        name_mapping = dict(n5=slice(4, None), n4=3, n3=2, n2=1, n1=0)
        return pp.SplittableInt(value, name_mapping)

    def test_no_land_mask(self):
        with mock.patch('numpy.frombuffer',
                        return_value=np.arange(3)):
            with self.assertRaises(ValueError) as err:
                pp._data_bytes_to_shaped_array(mock.Mock(),
                                               self.create_lbpack(120), None,
                                               (3, 4), np.dtype('>f4'),
                                               -999, mask=None)
            self.assertEqual(str(err.exception),
                             ('No mask was found to unpack the data. '
                              'Could not load.'))

    def test_land_mask(self):
        # Check basic land unpacking.
        field_data = self.land_masked_data
        result = self.check_read_data(field_data, 120, self.land_mask)
        self.assertMaskedArrayEqual(result, self.decomp_land_data)

    def test_land_masked_data_too_long(self):
        # Check land unpacking with field data that is larger than the mask.
        field_data = np.tile(self.land_masked_data, 2)
        result = self.check_read_data(field_data, 120, self.land_mask)
        self.assertMaskedArrayEqual(result, self.decomp_land_data)

    def test_sea_mask(self):
        # Check basic land unpacking.
        field_data = self.sea_masked_data
        result = self.check_read_data(field_data, 220, self.land_mask)
        self.assertMaskedArrayEqual(result, self.decomp_sea_data)

    def test_sea_masked_data_too_long(self):
        # Check sea unpacking with field data that is larger than the mask.
        field_data = np.tile(self.sea_masked_data, 2)
        result = self.check_read_data(field_data, 220, self.land_mask)
        self.assertMaskedArrayEqual(result, self.decomp_sea_data)

    def test_bad_lbpack(self):
        # Check basic land unpacking.
        field_data = self.sea_masked_data
        with self.assertRaises(ValueError):
            self.check_read_data(field_data, 320, self.land_mask)

    def check_read_data(self, field_data, lbpack, mask):
        # Calls pp._data_bytes_to_shaped_array with the necessary mocked
        # items, an lbpack instance, the correct data shape and mask instance.
        with mock.patch('numpy.frombuffer', return_value=field_data):
            return pp._data_bytes_to_shaped_array(mock.Mock(),
                                                  self.create_lbpack(lbpack),
                                                  None,
                                                  mask.shape, np.dtype('>f4'),
                                                  -999, mask=mask)


if __name__ == "__main__":
    tests.main()
