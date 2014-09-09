# (C) British Crown Copyright 2014, Met Office
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
"""Test function :func:`iris.fileformats.grib._load_convert.convert`."""

# import iris tests first so that some things can be initialised
# before importing anything else.
import iris.tests as tests

import mock

import iris
from iris.exceptions import TranslationError
from iris.fileformats.grib._message import _GribMessage
from iris.fileformats.grib._load_convert import convert


def _message(sections):
    return _GribMessage(mock.Mock(sections=sections))


class Test(tests.IrisTest):
    def test_call(self):
        sections = [{'editionNumber': 2}]
        field = _message(sections)
        this = 'iris.fileformats.grib._load_convert.grib2_convert'
        factory = mock.sentinel.factory
        func = lambda field, metadata: metadata['factories'].append(factory)
        with mock.patch(this, side_effect=func) as grib2_convert:
            result = convert(field)
            self.assertTrue(grib2_convert.called)
            metadata = ([factory], [], None, None, None, {}, [], [], [])
            self.assertEqual(result, metadata)

    def test_edition_1(self):
        sections = [{'editionNumber': 1}]
        field = _message(sections)
        with self.assertRaisesRegexp(TranslationError,
                                     'edition 1 is not supported'):
            convert(field)


if __name__ == '__main__':
    tests.main()
