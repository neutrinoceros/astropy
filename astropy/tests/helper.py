# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""
This module provides the tools used to internally run the astropy test suite
from the installed astropy.  It makes use of the |pytest| testing framework.
"""

from __future__ import annotations

import os
import pickle
from typing import TYPE_CHECKING

import numpy as np
import pytest

from astropy.units import allclose as quantity_allclose
from astropy.utils.introspection import minversion

# For backward-compatibility with affiliated packages
from .runner import TestRunner  # noqa: F401

if TYPE_CHECKING:
    from typing import Any

    from astropy.table.typing import MixinColumn


__all__ = [
    "assert_follows_unicode_guidelines",
    "assert_quantity_allclose",
    "check_pickling_recovery",
    "pickle_protocol",
    "generic_recursive_equality_test",
]

PYTEST_LT_8_0 = not minversion(pytest, "8.0")

# https://docs.github.com/en/actions/learn-github-actions/variables#default-environment-variables
CI = os.environ.get("CI", "false") == "true"
IS_CRON = os.environ.get("IS_CRON", "false") == "true"


def _save_coverage(cov, result, rootdir, testing_path):
    """
    This method is called after the tests have been run in coverage mode
    to cleanup and then save the coverage data and report.
    """
    from astropy.utils.console import color_print

    if result != 0:
        return

    # The coverage report includes the full path to the temporary
    # directory, so we replace all the paths with the true source
    # path. Note that this will not work properly for packages that still
    # rely on 2to3.
    try:
        # Coverage 4.0: _harvest_data has been renamed to get_data, the
        # lines dict is private
        cov.get_data()
    except AttributeError:
        # Coverage < 4.0
        cov._harvest_data()
        lines = cov.data.lines
    else:
        lines = cov.data._lines

    for key in list(lines.keys()):
        new_path = os.path.relpath(
            os.path.realpath(key), os.path.realpath(testing_path)
        )
        new_path = os.path.abspath(os.path.join(rootdir, new_path))
        lines[new_path] = lines.pop(key)

    color_print("Saving coverage data in .coverage...", "green")
    cov.save()

    color_print("Saving HTML coverage report in htmlcov...", "green")
    cov.html_report(directory=os.path.join(rootdir, "htmlcov"))


def assert_follows_unicode_guidelines(x, roundtrip=None):
    """
    Test that an object follows our Unicode policy.  See
    "Unicode guidelines" in the coding guidelines.

    Parameters
    ----------
    x : object
        The instance to test

    roundtrip : module, optional
        When provided, this namespace will be used to evaluate
        ``repr(x)`` and ensure that it roundtrips.  It will also
        ensure that ``__bytes__(x)`` roundtrip.
        If not provided, no roundtrip testing will be performed.
    """
    from astropy import conf

    with conf.set_temp("unicode_output", False):
        bytes_x = bytes(x)
        unicode_x = str(x)
        repr_x = repr(x)

        assert isinstance(bytes_x, bytes)
        bytes_x.decode("ascii")
        assert isinstance(unicode_x, str)
        unicode_x.encode("ascii")
        assert isinstance(repr_x, str)
        if isinstance(repr_x, bytes):
            repr_x.decode("ascii")
        else:
            repr_x.encode("ascii")

        if roundtrip is not None:
            assert x.__class__(bytes_x) == x
            assert x.__class__(unicode_x) == x
            assert eval(repr_x, roundtrip) == x

    with conf.set_temp("unicode_output", True):
        bytes_x = bytes(x)
        unicode_x = str(x)
        repr_x = repr(x)

        assert isinstance(bytes_x, bytes)
        bytes_x.decode("ascii")
        assert isinstance(unicode_x, str)
        assert isinstance(repr_x, str)
        if isinstance(repr_x, bytes):
            repr_x.decode("ascii")
        else:
            repr_x.encode("ascii")

        if roundtrip is not None:
            assert x.__class__(bytes_x) == x
            assert x.__class__(unicode_x) == x
            assert eval(repr_x, roundtrip) == x


@pytest.fixture(params=[0, 1, -1])
def pickle_protocol(request):
    """
    Fixture to run all the tests for protocols 0 and 1, and -1 (most advanced).
    (Originally from astropy.table.tests.test_pickle).
    """
    return request.param


def generic_recursive_equality_test(a, b, class_history):
    """
    Check if the attributes of a and b are equal. Then,
    check if the attributes of the attributes are equal.
    """
    # NOTE: The call may need to be adapted if other objects implementing a __getstate__
    # with required argument(s) are passed to this function.
    # For a class with `__slots__` the default state is not a `dict`;
    # with neither `__dict__` nor `__slots__` it is `None`.
    state = a.__getstate__(a) if isinstance(a, type) else a.__getstate__()
    dict_a = state if isinstance(state, dict) else getattr(a, "__dict__", dict())
    dict_b = b.__dict__
    for key in dict_a:
        assert key in dict_b, f"Did not pickle {key}"

        if dict_a[key].__class__.__eq__ is not object.__eq__:
            # Only compare if the class defines a proper equality test.
            # E.g., info does not define __eq__, and hence defers to
            # object.__eq__, which is equivalent to checking that two
            # instances are the same.  This will generally not be true
            # after pickling.
            eq = dict_a[key] == dict_b[key]
            if "__iter__" in dir(eq):
                eq = False not in eq
            assert eq, f"Value of {key} changed by pickling"

        if hasattr(dict_a[key], "__dict__"):
            if dict_a[key].__class__ in class_history:
                # attempt to prevent infinite recursion
                pass
            else:
                new_class_history = [dict_a[key].__class__]
                new_class_history.extend(class_history)
                generic_recursive_equality_test(
                    dict_a[key], dict_b[key], new_class_history
                )


def check_pickling_recovery(original, protocol):
    """
    Try to pickle an object. If successful, make sure
    the object's attributes survived pickling and unpickling.
    """
    f = pickle.dumps(original, protocol=protocol)
    unpickled = pickle.loads(f)
    class_history = [original.__class__]
    generic_recursive_equality_test(original, unpickled, class_history)


def assert_quantity_allclose(actual, desired, rtol=1.0e-7, atol=None, **kwargs):
    """
    Raise an assertion if two objects are not equal up to desired tolerance.

    This is a :class:`~astropy.units.Quantity`-aware version of
    :func:`numpy.testing.assert_allclose`.
    """
    from astropy.units.quantity import _unquantify_allclose_arguments

    __tracebackhide__ = True
    np.testing.assert_allclose(
        *_unquantify_allclose_arguments(actual, desired, rtol, atol), **kwargs
    )


def _assert_mixin_columns_equal(
    actual: MixinColumn,
    desired: MixinColumn,
    /,
    *,
    attrs: list[str] | None = None,
    compare_class: bool = True,
    rtol: float = 1e-15,
    **kwargs: Any,
) -> None:
    """Compare mixin columns by their shape and attributes, including those provided by .info

    Parameters
    ----------
    actual and desired: MixinColumn (positional only)
        these objects must have attributes `shape` and `info`.
        Typically this means astropy ndarray subclasses or
        :class:`astropy.utils.shapes.ShapedLikeNDArray`.

    attrs: list[str] (optional, keyword only)
        a list of attributes to compare in addition to the default list:
        ['info.name', 'info.format', 'info.unit',
        'info.description', 'info.meta', 'info.dtype']

    compare_class: bool (default: False, keyword only)
        Whether to check that the two objects are instances of the same class

    rtol: float (default: 1e-15)
        Relative tolerance on array comparison.
        Passed down to :func:`numpy.testing.assert_allclose`.

    **kwargs: dict, optional
        Extra arguments to :func:`numpy.testing.assert_allclose`/

    Raises
    ------
    AssertionError
        If actual doesn't compare equal to desired.
    """
    if compare_class:
        assert actual.__class__ is desired.__class__

    assert actual.shape == desired.shape

    info_attrs = [
        "info.name",
        "info.format",
        "info.unit",
        "info.description",
        "info.meta",
        "info.dtype",
    ]
    for attr in info_attrs + (attrs or []):
        a1 = actual
        a2 = desired
        for subattr in attr.split("."):
            try:
                a1 = getattr(a1, subattr)
                a2 = getattr(a2, subattr)
            except AttributeError:
                a1 = a1[subattr]
                a2 = a2[subattr]

        # MixinColumn info.meta can None instead of empty OrderedDict(), #6720 would
        # fix this.
        if attr == "info.meta":
            a1 = {} if a1 is None else a1
            a2 = {} if a2 is None else a2

        if isinstance(a1, np.ndarray) and a1.dtype.kind == "f":
            assert_quantity_allclose(a1, a2, rtol=rtol, **kwargs)
        elif isinstance(a1, np.dtype):
            # FITS does not perfectly preserve dtype: byte order can change, and
            # unicode gets stored as bytes.  So, we just check safe casting, to
            # ensure we do not, e.g., accidentally change integer to float, etc.
            assert np.can_cast(a2, a1, casting="safe")
        else:
            assert np.all(a1 == a2)

    # For no attrs that means we just compare directly.
    if not attrs:
        if isinstance(actual, np.ndarray) and actual.dtype.kind == "f":
            assert quantity_allclose(actual, desired, rtol=1e-15)
        else:
            assert np.all(actual == desired)
