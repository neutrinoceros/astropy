# Licensed under a 3-clause BSD style license. See LICENSE.rst except
# for parts explicitly labelled as being (largely) copies of numpy
# implementations; for those, see licenses/NUMPY_LICENSE.rst.
"""Helpers for overriding numpy functions.

We override numpy functions in `~astropy.units.Quantity.__array_function__`.
In this module, the numpy functions are split in four groups, each of
which has an associated `set` or `dict`:

1. SUBCLASS_SAFE_FUNCTIONS (set), if the numpy implementation
   supports Quantity; we pass on to ndarray.__array_function__.
2. FUNCTION_HELPERS (dict), if the numpy implementation is usable
   after converting quantities to arrays with suitable units,
   and possibly setting units on the result.
3. DISPATCHED_FUNCTIONS (dict), if the function makes sense but
   requires a Quantity-specific implementation
4. UNSUPPORTED_FUNCTIONS (set), if the function does not make sense.

For the FUNCTION_HELPERS `dict`, the value is a function that does the
unit conversion.  It should take the same arguments as the numpy
function would (though one can use ``*args`` and ``**kwargs``) and
return a tuple of ``args, kwargs, unit, out``, where ``args`` and
``kwargs`` will be will be passed on to the numpy implementation,
``unit`` is a possible unit of the result (`None` if it should not be
converted to Quantity), and ``out`` is a possible output Quantity passed
in, which will be filled in-place.

For the DISPATCHED_FUNCTIONS `dict`, the value is a function that
implements the numpy functionality for Quantity input. It should
return a tuple of ``result, unit, out``, where ``result`` is generally
a plain array with the result, and ``unit`` and ``out`` are as above.
If unit is `None`, result gets returned directly, so one can also
return a Quantity directly using ``quantity_result, None, None``.

"""

import functools
import operator

import numpy as np
from numpy.lib import recfunctions as rfn

from astropy.units.core import dimensionless_unscaled
from astropy.units.errors import UnitConversionError, UnitsError, UnitTypeError
from astropy.utils.compat import (
    COPY_IF_NEEDED,
    NUMPY_LT_2_0,
    NUMPY_LT_2_1,
    NUMPY_LT_2_2,
)

if NUMPY_LT_2_0:
    import numpy.core as np_core
else:
    import numpy._core as np_core

# In 1.17, overrides are enabled by default, but it is still possible to
# turn them off using an environment variable.  We use getattr since it
# is planned to remove that possibility in later numpy versions.
ARRAY_FUNCTION_ENABLED = getattr(np_core.overrides, "ENABLE_ARRAY_FUNCTION", True)
SUBCLASS_SAFE_FUNCTIONS = set()
"""Functions with implementations supporting subclasses like Quantity."""
FUNCTION_HELPERS = {}
"""Functions with implementations usable with proper unit conversion."""
DISPATCHED_FUNCTIONS = {}
"""Functions for which we provide our own implementation."""

if NUMPY_LT_2_2:
    # in numpy 2.2 these are auto detected by numpy itself
    # xref https://github.com/numpy/numpy/issues/27451
    SUPPORTED_NEP35_FUNCTIONS = {
        np.arange,
        np.empty, np.ones, np.zeros, np.full,
        np.array, np.asarray, np.asanyarray, np.ascontiguousarray, np.asfortranarray,
        np.frombuffer, np.fromfile, np.fromfunction, np.fromiter, np.fromstring,
        np.require, np.identity, np.eye, np.tri, np.genfromtxt, np.loadtxt,
    }  # fmt: skip
    """Functions that support a 'like' keyword argument and dispatch on it (NEP 35)"""
else:
    # When our minimum becomes numpy>=2.2, this can be removed, here and in the tests
    SUPPORTED_NEP35_FUNCTIONS = set()

"""Functions that support a 'like' keyword argument and dispatch on it (NEP 35)"""
UNSUPPORTED_FUNCTIONS = set()
"""Functions that cannot sensibly be used with quantities."""
SUBCLASS_SAFE_FUNCTIONS |= {
    np.shape, np.size, np.ndim,
    np.reshape, np.ravel, np.moveaxis, np.rollaxis, np.swapaxes,
    np.transpose, np.atleast_1d, np.atleast_2d, np.atleast_3d,
    np.expand_dims, np.squeeze, np.broadcast_to, np.broadcast_arrays,
    np.flip, np.fliplr, np.flipud, np.rot90,
    np.argmin, np.argmax, np.argsort, np.lexsort, np.searchsorted,
    np.nonzero, np.argwhere, np.flatnonzero,
    np.diag_indices_from, np.triu_indices_from, np.tril_indices_from,
    np.real, np.imag, np.diagonal, np.diagflat, np.empty_like,
    np.compress, np.extract, np.delete, np.trim_zeros, np.roll, np.take,
    np.put, np.fill_diagonal, np.tile, np.repeat,
    np.split, np.array_split, np.hsplit, np.vsplit, np.dsplit,
    np.stack, np.column_stack, np.hstack, np.vstack, np.dstack,
    np.max, np.min, np.amax, np.amin, np.ptp, np.sum, np.cumsum,
    np.prod, np.cumprod,
    np.round, np.around,
    np.fix, np.angle, np.i0, np.clip,
    np.isposinf, np.isneginf, np.isreal, np.iscomplex,
    np.average, np.mean, np.std, np.var, np.trace,
    np.nanmax, np.nanmin, np.nanargmin, np.nanargmax, np.nanmean,
    np.nansum, np.nancumsum, np.nanprod, np.nancumprod,
    np.einsum_path, np.linspace,
    np.sort, np.partition, np.meshgrid,
    np.common_type, np.result_type, np.can_cast, np.min_scalar_type,
    np.iscomplexobj, np.isrealobj,
    np.shares_memory, np.may_share_memory,
    np.apply_along_axis, np.take_along_axis, np.put_along_axis,
    np.linalg.cond, np.linalg.multi_dot,
}  # fmt: skip

SUBCLASS_SAFE_FUNCTIONS |= {np.median}

if NUMPY_LT_2_0:
    # functions (re)moved in numpy 2.0; alias for np.round in NUMPY_LT_1_25
    SUBCLASS_SAFE_FUNCTIONS |= {
        np.msort,
        np.round_,  # noqa: NPY003, NPY201
        np.trapz,  # noqa: NPY201
        np.product,  # noqa: NPY003, NPY201
        np.cumproduct,  # noqa: NPY003, NPY201
    }
if not NUMPY_LT_2_0:
    # Array-API compatible versions (matrix axes always at end).
    SUBCLASS_SAFE_FUNCTIONS |= {
        np.matrix_transpose, np.linalg.matrix_transpose,
        np.linalg.diagonal, np.linalg.trace,
        np.linalg.matrix_norm, np.linalg.vector_norm, np.linalg.vecdot,
    }  # fmt: skip

    # these work out of the box (and are tested), because they
    # delegate to other, already wrapped functions from the np namespace
    SUBCLASS_SAFE_FUNCTIONS |= {
        np.linalg.cross, np.linalg.svdvals, np.linalg.tensordot, np.linalg.matmul,
        np.unique_all, np.unique_counts, np.unique_inverse, np.unique_values,
        np.astype,
    }  # fmt: skip

    # trapz was renamed to trapezoid
    SUBCLASS_SAFE_FUNCTIONS |= {np.trapezoid}
if not NUMPY_LT_2_1:
    SUBCLASS_SAFE_FUNCTIONS |= {np.unstack, np.cumulative_prod, np.cumulative_sum}

# Implemented as methods on Quantity:
# np.ediff1d is from setops, but we support it anyway; the others
# currently return NotImplementedError.
# TODO: move latter to UNSUPPORTED? Would raise TypeError instead.
SUBCLASS_SAFE_FUNCTIONS |= {np.ediff1d}
UNSUPPORTED_FUNCTIONS |= {
    np.packbits, np.unpackbits, np.unravel_index,
    np.ravel_multi_index, np.ix_, np.cov, np.corrcoef,
    np.busday_count, np.busday_offset, np.datetime_as_string,
    np.is_busday, np.all, np.any,
}  # fmt: skip

if NUMPY_LT_2_0:
    UNSUPPORTED_FUNCTIONS |= {  # removed in numpy 2.0
        np.sometrue, np.alltrue,  # noqa: NPY003, NPY201
    }  # fmt: skip

# Could be supported if we had a natural logarithm unit.
UNSUPPORTED_FUNCTIONS |= {np.linalg.slogdet}
TBD_FUNCTIONS = {
    rfn.drop_fields, rfn.rename_fields, rfn.append_fields, rfn.join_by,
    rfn.apply_along_fields, rfn.assign_fields_by_name,
    rfn.find_duplicates, rfn.recursive_fill_fields, rfn.require_fields,
    rfn.repack_fields, rfn.stack_arrays,
}  # fmt: skip
UNSUPPORTED_FUNCTIONS |= TBD_FUNCTIONS
IGNORED_FUNCTIONS = {
    # I/O - useless for Quantity, since no way to store the unit.
    np.save, np.savez, np.savetxt, np.savez_compressed,
    # Polynomials
    np.poly, np.polyadd, np.polyder, np.polydiv, np.polyfit, np.polyint,
    np.polymul, np.polysub, np.polyval, np.roots, np.vander,
    # functions taking record arrays (which are deprecated)
    rfn.rec_append_fields, rfn.rec_drop_fields, rfn.rec_join,
}  # fmt: skip
UNSUPPORTED_FUNCTIONS |= IGNORED_FUNCTIONS


class FunctionAssigner:
    def __init__(self, assignments):
        self.assignments = assignments

    def __call__(self, f=None, helps=None, module=np):
        """Add a helper to a numpy function.

        Normally used as a decorator.

        If ``helps`` is given, it should be the numpy function helped (or an
        iterable of numpy functions helped).

        If ``helps`` is not given, it is assumed the function helped is the
        numpy function with the same name as the decorated function.
        """
        if f is not None:
            if helps is None:
                helps = getattr(module, f.__name__)
            if not np.iterable(helps):
                helps = (helps,)
            for h in helps:
                self.assignments[h] = f
            return f
        elif helps is not None or module is not np:
            return functools.partial(self.__call__, helps=helps, module=module)
        else:  # pragma: no cover
            raise ValueError("function_helper requires at least one argument.")


function_helper = FunctionAssigner(FUNCTION_HELPERS)

dispatched_function = FunctionAssigner(DISPATCHED_FUNCTIONS)


@function_helper(
    helps={
        np.copy, np.real_if_close, np.sort_complex, np.resize,
        np.fft.fft, np.fft.ifft, np.fft.rfft, np.fft.irfft,
        np.fft.fft2, np.fft.ifft2, np.fft.rfft2, np.fft.irfft2,
        np.fft.fftn, np.fft.ifftn, np.fft.rfftn, np.fft.irfftn,
        np.fft.hfft, np.fft.ihfft,
        np.linalg.eigvals, np.linalg.eigvalsh,
    } | ({np.asfarray} if NUMPY_LT_2_0 else set())  # noqa: NPY201
)  # fmt: skip
def invariant_a_helper(a, *args, **kwargs):
    return (a.view(np.ndarray),) + args, kwargs, a.unit, None


@function_helper(helps={np.tril, np.triu})
def invariant_m_helper(m, *args, **kwargs):
    return (m.view(np.ndarray),) + args, kwargs, m.unit, None


@function_helper(helps={np.fft.fftshift, np.fft.ifftshift})
def invariant_x_helper(x, *args, **kwargs):
    return (x.view(np.ndarray),) + args, kwargs, x.unit, None


# Note that ones_like does *not* work by default since if one creates an empty
# array with a unit, one cannot just fill it with unity.  Indeed, in this
# respect, it is a bit of an odd function for Quantity. On the other hand, it
# matches the idea that a unit is the same as the quantity with that unit and
# value of 1. Also, it used to work without __array_function__.
# zeros_like does work by default for regular quantities, because numpy first
# creates an empty array with the unit and then fills it with 0 (which can have
# any unit), but for structured dtype this fails (0 cannot have an arbitrary
# structured unit), so we include it here too.
@function_helper(helps={np.ones_like, np.zeros_like})
def like_helper(a, *args, **kwargs):
    subok = args[2] if len(args) > 2 else kwargs.pop("subok", True)
    unit = a.unit if subok else None
    return (a.view(np.ndarray),) + args, kwargs, unit, None


def _quantity_out_as_array(out):
    from astropy.units import Quantity

    if isinstance(out, Quantity):
        return out.view(np.ndarray)
    else:
        # TODO: for an ndarray output, one could in principle
        # try converting the input to dimensionless.
        raise NotImplementedError


# nanvar is safe for Quantity and was previously in SUBCLASS_FUNCTIONS, but it
# is not safe for Angle, since the resulting unit is inconsistent with being
# an Angle. By using FUNCTION_HELPERS, the unit gets passed through
# _result_as_quantity, which will correctly drop to Quantity.
# A side effect would be that np.nanstd then also produces Quantity; this
# is avoided by it being helped below.
@function_helper
def nanvar(a, axis=None, dtype=None, out=None, ddof=0, keepdims=np._NoValue, **kwargs):
    a = _as_quantity(a)
    out_array = None if out is None else _quantity_out_as_array(out)
    return (
        (a.view(np.ndarray), axis, dtype, out_array, ddof, keepdims),
        kwargs,
        a.unit**2,
        out,
    )


@function_helper
def nanstd(a, axis=None, dtype=None, out=None, ddof=0, keepdims=np._NoValue, **kwargs):
    a = _as_quantity(a)
    out_array = None if out is None else _quantity_out_as_array(out)
    return (
        (a.view(np.ndarray), axis, dtype, out_array, ddof, keepdims),
        kwargs,
        a.unit,
        out,
    )


@function_helper
def sinc(x):
    from astropy.units.si import radian

    try:
        x = x.to_value(radian)
    except UnitsError:
        raise UnitTypeError(
            "Can only apply 'sinc' function to quantities with angle units"
        )
    return (x,), {}, dimensionless_unscaled, None


@dispatched_function
def unwrap(p, discont=None, axis=-1, *, period=2 * np.pi):
    from astropy.units.si import radian

    if discont is None:
        discont = np.pi << radian

    if period == 2 * np.pi:
        period <<= radian

    p, discont, period = _as_quantities(p, discont, period)
    result = np.unwrap.__wrapped__(
        p.to_value(radian),
        discont.to_value(radian),
        axis=axis,
        period=period.to_value(radian),
    )
    result = radian.to(p.unit, result)
    return result, p.unit, None


@function_helper
def argpartition(a, *args, **kwargs):
    return (a.view(np.ndarray),) + args, kwargs, None, None


@function_helper
def full_like(a, fill_value, *args, **kwargs):
    unit = a.unit if kwargs.get("subok", True) else None
    return (a.view(np.ndarray), a._to_own_unit(fill_value)) + args, kwargs, unit, None


@function_helper
def putmask(a, mask, values):
    from astropy.units import Quantity

    if isinstance(a, Quantity):
        return (a.view(np.ndarray), mask, a._to_own_unit(values)), {}, a.unit, None
    elif isinstance(values, Quantity):
        return (a, mask, values.to_value(dimensionless_unscaled)), {}, None, None
    else:
        raise NotImplementedError


@function_helper
def place(arr, mask, vals):
    from astropy.units import Quantity

    if isinstance(arr, Quantity):
        return (arr.view(np.ndarray), mask, arr._to_own_unit(vals)), {}, arr.unit, None
    elif isinstance(vals, Quantity):
        return (arr, mask, vals.to_value(dimensionless_unscaled)), {}, None, None
    else:
        raise NotImplementedError


@function_helper
def copyto(dst, src, *args, **kwargs):
    from astropy.units import Quantity

    if isinstance(dst, Quantity):
        return (dst.view(np.ndarray), dst._to_own_unit(src)) + args, kwargs, None, None
    elif isinstance(src, Quantity):
        return (dst, src.to_value(dimensionless_unscaled)) + args, kwargs, None, None
    else:
        raise NotImplementedError


@function_helper
def nan_to_num(x, copy=True, nan=0.0, posinf=None, neginf=None):
    nan = x._to_own_unit(nan)
    if posinf is not None:
        posinf = x._to_own_unit(posinf)
    if neginf is not None:
        neginf = x._to_own_unit(neginf)
    return (
        (x.view(np.ndarray),),
        dict(copy=True, nan=nan, posinf=posinf, neginf=neginf),
        x.unit,
        None,
    )


def _as_quantity(a):
    """Convert argument to a Quantity (or raise NotImplementedError)."""
    from astropy.units import Quantity

    try:
        return Quantity(a, copy=COPY_IF_NEEDED, subok=True)
    except Exception:
        # If we cannot convert to Quantity, we should just bail.
        raise NotImplementedError


def _as_quantities(*args):
    """Convert arguments to Quantity (or raise NotImplentedError)."""
    from astropy.units import Quantity

    try:
        # Note: this should keep the dtype the same
        return tuple(
            Quantity(a, copy=COPY_IF_NEEDED, subok=True, dtype=None) for a in args
        )
    except Exception:
        # If we cannot convert to Quantity, we should just bail.
        raise NotImplementedError


def _quantities2arrays(*args, unit_from_first=False):
    """Convert to arrays in units of the first argument that has a unit.

    If unit_from_first, take the unit of the first argument regardless
    whether it actually defined a unit (e.g., dimensionless for arrays).
    """
    # Turn first argument into a quantity.
    q = _as_quantity(args[0])
    if len(args) == 1:
        return (q.value,), q.unit

    # If we care about the unit being explicit, then check whether this
    # argument actually had a unit, or was likely inferred.
    if not unit_from_first and (
        q.unit is q._default_unit and not hasattr(args[0], "unit")
    ):
        # Here, the argument could still be things like [10*u.one, 11.*u.one]),
        # i.e., properly dimensionless.  So, we only override with anything
        # that has a unit not equivalent to dimensionless (fine to ignore other
        # dimensionless units pass, even if explicitly given).
        for arg in args[1:]:
            trial = _as_quantity(arg)
            if not trial.unit.is_equivalent(q.unit):
                # Use any explicit unit not equivalent to dimensionless.
                q = trial
                break

    # We use the private _to_own_unit method here instead of just
    # converting everything to quantity and then do .to_value(qs0.unit)
    # as we want to allow arbitrary unit for 0, inf, and nan.
    try:
        arrays = tuple((q._to_own_unit(arg)) for arg in args)
    except TypeError:
        raise NotImplementedError

    return arrays, q.unit


def _iterable_helper(*args, out=None, **kwargs):
    """Convert arguments to Quantity, and treat possible 'out'."""
    if out is not None:
        kwargs["out"] = _quantity_out_as_array(out)  # raises if not Quantity.

    arrays, unit = _quantities2arrays(*args)
    return arrays, kwargs, unit, out


@function_helper
def concatenate(arrays, axis=0, out=None, **kwargs):
    # TODO: make this smarter by creating an appropriately shaped
    # empty output array and just filling it.
    arrays, kwargs, unit, out = _iterable_helper(*arrays, out=out, axis=axis, **kwargs)
    return (arrays,), kwargs, unit, out


def _block(arrays, max_depth, result_ndim, depth=0):
    # Block by concatenation, copied from np._core.shape_base,
    # but ensuring that we call regular concatenate.
    if depth < max_depth:
        arrs = [_block(arr, max_depth, result_ndim, depth + 1) for arr in arrays]
        # The one difference with the numpy code.
        return np.concatenate(arrs, axis=-(max_depth - depth))
    else:
        return np_core.shape_base._atleast_nd(arrays, result_ndim)


UNIT_FROM_LIKE_ARG = object()

if NUMPY_LT_2_0:

    @function_helper
    def arange(*args, start=None, stop=None, step=None, dtype=None):
        return arange_impl(*args, start=start, stop=stop, step=step, dtype=dtype)
else:

    @function_helper
    def arange(*args, start=None, stop=None, step=None, dtype=None, device=None):
        return arange_impl(
            *args, start=start, stop=stop, step=step, dtype=dtype, device=device
        )


def arange_impl(*args, start=None, stop=None, step=None, dtype=None, **kwargs):
    # NumPy is supposed to validate the input parameters before this dispatched
    # function is reached. Nevertheless, we'll sprinkle a few rundundant
    # sanity checks in the form of `assert` statements.
    # As they are not part of the business logic, it is fine if they are
    # compiled-away (e.g. the Python interpreter runs with -O)
    assert len(args) <= 4

    # bind positional arguments to their meaningful names
    # following the (complex) logic of np.arange
    match args:
        case (pos1,):
            assert stop is None or start is None
            if stop is None:
                stop = pos1
            elif start is None:
                start = pos1
        case start, stop, *rest:
            if start is not None and stop is None:
                start, stop = stop, start
            match rest:
                # rebind step and dtype if possible
                case (step,):
                    pass
                case step, dtype:
                    pass

    # as the only required argument, we want stop to set the unit of the output
    # so it's important that it comes first in the qty_kwargs
    qty_kwargs = {
        k: v
        for k, v in (("stop", stop), ("start", start), ("step", step))
        if v is not None
    }
    out_unit = getattr(stop, "unit", UNIT_FROM_LIKE_ARG)
    if out_unit is UNIT_FROM_LIKE_ARG:
        if hasattr(start, "unit") or hasattr(step, "unit"):
            raise TypeError(
                "stop without a unit cannot be combined with start or step with a unit."
            )
        kwargs.update(qty_kwargs)
    else:
        # Convert possible start, step to stop units.
        new_values, _ = _quantities2arrays(*qty_kwargs.values())
        kwargs.update(zip(qty_kwargs.keys(), new_values))

    kwargs["dtype"] = dtype
    return (), kwargs, out_unit, None


if NUMPY_LT_2_0:

    @function_helper(helps={np.empty, np.ones, np.zeros})
    def creation_helper(shape, dtype=None, order="C"):
        return (shape, dtype, order), {}, UNIT_FROM_LIKE_ARG, None
else:

    @function_helper(helps={np.empty, np.ones, np.zeros})
    def creation_helper(shape, dtype=None, order="C", *, device=None):
        return (shape, dtype, order), {"device": device}, UNIT_FROM_LIKE_ARG, None


if NUMPY_LT_2_0:

    @function_helper
    def full(shape, fill_value, dtype=None, order="C"):
        return full_impl(shape, fill_value, dtype, order)
else:

    @function_helper
    def full(shape, fill_value, dtype=None, order="C", *, device=None):
        return full_impl(shape, fill_value, dtype, order, device=device)


def full_impl(shape, fill_value, *args, **kwargs):
    out_unit = getattr(fill_value, "unit", UNIT_FROM_LIKE_ARG)
    if out_unit is not UNIT_FROM_LIKE_ARG:
        fill_value = _as_quantity(fill_value).value
    return (shape, fill_value) + args, kwargs, out_unit, None


@function_helper
def require(a, dtype=None, requirements=None):
    out_unit = getattr(a, "unit", UNIT_FROM_LIKE_ARG)
    if out_unit is not UNIT_FROM_LIKE_ARG:
        a = _as_quantity(a).value
    return (a, dtype, requirements), {}, out_unit, None


@function_helper
def array(object, dtype=None, *, copy=True, order="K", subok=False, ndmin=0):
    out_unit = getattr(object, "unit", UNIT_FROM_LIKE_ARG)
    if out_unit is not UNIT_FROM_LIKE_ARG:
        object = _as_quantity(object).value
    kwargs = {"copy": copy, "order": order, "subok": subok, "ndmin": ndmin}
    return (object, dtype), kwargs, out_unit, None


if NUMPY_LT_2_0:
    asarray_impl_1_helps = {np.asarray, np.asanyarray}
    asarray_impl_2_helps = {}
elif NUMPY_LT_2_1:
    asarray_impl_1_helps = {np.asanyarray}
    asarray_impl_2_helps = {np.asarray}
else:
    asarray_impl_1_helps = {}
    asarray_impl_2_helps = {np.asarray, np.asanyarray}


@function_helper(helps=asarray_impl_1_helps)
def asarray_impl_1(a, dtype=None, order=None):
    out_unit = getattr(a, "unit", UNIT_FROM_LIKE_ARG)
    if out_unit is not UNIT_FROM_LIKE_ARG:
        a = _as_quantity(a).value
    return (a, dtype, order), {}, out_unit, None


@function_helper(helps=asarray_impl_2_helps)
def asarray_impl_2(a, dtype=None, order=None, *, device=None, copy=None):
    out_unit = getattr(a, "unit", UNIT_FROM_LIKE_ARG)
    if out_unit is not UNIT_FROM_LIKE_ARG:
        a = _as_quantity(a).value
    return (a, dtype, order), {"device": device, "copy": copy}, out_unit, None


@function_helper(helps={np.ascontiguousarray, np.asfortranarray})
def aslayoutarray_helper(a, dtype=None):
    out_unit = getattr(a, "unit", UNIT_FROM_LIKE_ARG)
    if out_unit is not UNIT_FROM_LIKE_ARG:
        a = _as_quantity(a).value
    return (a, dtype), {}, out_unit, None


@function_helper
def fromfunction(function, shape, *, dtype=float, **kwargs):
    zero_arg = np.zeros(len(shape), dtype)
    try:
        out_unit = function(*zero_arg).unit
    except Exception:
        out_unit = UNIT_FROM_LIKE_ARG
    return (function, shape), {"dtype": dtype, **kwargs}, out_unit, None


@function_helper(helps={
        np.frombuffer, np.fromfile, np.fromiter, np.fromstring,
        np.identity, np.eye, np.tri,
        np.genfromtxt, np.loadtxt,
    }
)  # fmt: skip
def generic_like_array_function_helper(*args, **kwargs):
    return args, kwargs, UNIT_FROM_LIKE_ARG, None


@dispatched_function
def block(arrays):
    # We need to override block since the numpy implementation can take two
    # different paths, one for concatenation, one for creating a large empty
    # result array in which parts are set.  Each assumes array input and
    # cannot be used directly.  Since it would be very costly to inspect all
    # arrays and then turn them back into a nested list, we just copy here the
    # first implementation, np.core.shape_base._block, which is the easiest to
    # adjust while making sure that both units and class are properly kept.
    (arrays, list_ndim, result_ndim, final_size) = np_core.shape_base._block_setup(
        arrays
    )
    result = _block(arrays, list_ndim, result_ndim)
    if list_ndim == 0:
        result = result.copy()
    return result, None, None


@function_helper
def choose(a, choices, out=None, mode="raise"):
    choices, kwargs, unit, out = _iterable_helper(*choices, out=out, mode=mode)
    return (a, choices), kwargs, unit, out


@function_helper
def select(condlist, choicelist, default=0):
    choicelist, kwargs, unit, out = _iterable_helper(*choicelist)
    if default != 0:
        default = (1 * unit)._to_own_unit(default)
    return (condlist, choicelist, default), kwargs, unit, out


@dispatched_function
def piecewise(x, condlist, funclist, *args, **kw):
    from astropy.units import Quantity

    # Copied implementation from numpy.lib._function_base_impl.piecewise,
    # taking care of units of function outputs.
    n2 = len(funclist)
    # undocumented: single condition is promoted to a list of one condition
    if np.isscalar(condlist) or (
        not isinstance(condlist[0], (list, np.ndarray)) and x.ndim != 0
    ):
        condlist = [condlist]

    if any(isinstance(c, Quantity) for c in condlist):
        raise NotImplementedError

    condlist = np.array(condlist, dtype=bool)
    n = len(condlist)

    if n == n2 - 1:  # compute the "otherwise" condition.
        condelse = ~np.any(condlist, axis=0, keepdims=True)
        condlist = np.concatenate([condlist, condelse], axis=0)
        n += 1
    elif n != n2:
        raise ValueError(
            f"with {n} condition(s), either {n} or {n + 1} functions are expected"
        )

    y = np.zeros(x.shape, x.dtype)
    where = []
    what = []
    for k in range(n):
        item = funclist[k]
        if not callable(item):
            where.append(condlist[k])
            what.append(item)
        else:
            vals = x[condlist[k]]
            if vals.size > 0:
                where.append(condlist[k])
                what.append(item(vals, *args, **kw))

    what, unit = _quantities2arrays(*what)
    for item, value in zip(where, what):
        y[item] = value

    return y, unit, None


@function_helper
def append(arr, values, *args, **kwargs):
    arrays, unit = _quantities2arrays(arr, values, unit_from_first=True)
    return arrays + args, kwargs, unit, None


@function_helper
def insert(arr, obj, values, *args, **kwargs):
    from astropy.units import Quantity

    if isinstance(obj, Quantity):
        raise NotImplementedError

    (arr, values), unit = _quantities2arrays(arr, values, unit_from_first=True)
    return (arr, obj, values) + args, kwargs, unit, None


@function_helper
def pad(array, pad_width, mode="constant", **kwargs):
    # pad dispatches only on array, so that must be a Quantity.
    for key in "constant_values", "end_values":
        value = kwargs.pop(key, None)
        if value is None:
            continue
        if not isinstance(value, tuple):
            value = (value,)

        new_value = []
        for v in value:
            new_value.append(
                tuple(array._to_own_unit(_v) for _v in v)
                if isinstance(v, tuple)
                else array._to_own_unit(v)
            )
        kwargs[key] = new_value

    return (array.view(np.ndarray), pad_width, mode), kwargs, array.unit, None


@function_helper
def where(condition, *args):
    from astropy.units import Quantity

    if isinstance(condition, Quantity) or len(args) != 2:
        raise NotImplementedError

    args, unit = _quantities2arrays(*args)
    return (condition,) + args, {}, unit, None


@function_helper(helps=({np.quantile, np.nanquantile}))
def quantile(a, q, *args, _q_unit=dimensionless_unscaled, **kwargs):
    if len(args) >= 2:
        out = args[1]
        args = args[:1] + args[2:]
    else:
        out = kwargs.pop("out", None)

    from astropy.units import Quantity

    if isinstance(q, Quantity):
        q = q.to_value(_q_unit)

    (a,), kwargs, unit, out = _iterable_helper(a, out=out, **kwargs)

    return (a, q) + args, kwargs, unit, out


@function_helper(helps={np.percentile, np.nanpercentile})
def percentile(a, q, *args, **kwargs):
    from astropy.units import percent

    return quantile(a, q, *args, _q_unit=percent, **kwargs)


@function_helper
def nanmedian(a, axis=None, out=None, overwrite_input=False, keepdims=np._NoValue):
    return _iterable_helper(
        a, axis=axis, out=out, overwrite_input=overwrite_input, keepdims=keepdims
    )


@function_helper
def count_nonzero(a, *args, **kwargs):
    return (a.value,) + args, kwargs, None, None


@function_helper(helps={np.isclose, np.allclose})
def close(a, b, rtol=1e-05, atol=1e-08, *args, **kwargs):
    from astropy.units import Quantity

    (a, b), unit = _quantities2arrays(a, b, unit_from_first=True)
    # Allow number without a unit as having the unit.
    atol = Quantity(atol, unit).value

    return (a, b, rtol, atol) + args, kwargs, None, None


@dispatched_function
def array_equal(a1, a2, equal_nan=False):
    try:
        args, unit = _quantities2arrays(a1, a2)
    except UnitConversionError:
        return False, None, None
    return np.array_equal(*args, equal_nan=equal_nan), None, None


@dispatched_function
def array_equiv(a1, a2):
    try:
        args, unit = _quantities2arrays(a1, a2)
    except UnitConversionError:
        return False, None, None
    return np.array_equiv(*args), None, None


@function_helper(helps={np.dot, np.outer})
def dot_like(a, b, out=None):
    from astropy.units import Quantity

    a, b = _as_quantities(a, b)
    unit = a.unit * b.unit
    if out is not None:
        if not isinstance(out, Quantity):
            raise NotImplementedError
        return tuple(x.view(np.ndarray) for x in (a, b, out)), {}, unit, out
    else:
        return (a.view(np.ndarray), b.view(np.ndarray)), {}, unit, None


@function_helper(
    helps={
        np.cross,
        np.kron,
        np.tensordot,
    }
)
def cross_like_a_b(a, b, *args, **kwargs):
    a, b = _as_quantities(a, b)
    unit = a.unit * b.unit
    return (a.view(np.ndarray), b.view(np.ndarray)) + args, kwargs, unit, None


@function_helper(
    helps={
        np.inner,
        np.vdot,
        np.correlate,
        np.convolve,
    }
)
def cross_like_a_v(a, v, *args, **kwargs):
    a, v = _as_quantities(a, v)
    unit = a.unit * v.unit
    return (a.view(np.ndarray), v.view(np.ndarray)) + args, kwargs, unit, None


@function_helper
def einsum(*operands, out=None, **kwargs):
    subscripts, *operands = operands

    if not isinstance(subscripts, str):
        raise ValueError('only "subscripts" string mode supported for einsum.')

    if out is not None:
        kwargs["out"] = _quantity_out_as_array(out)

    qs = _as_quantities(*operands)
    unit = functools.reduce(operator.mul, (q.unit for q in qs), dimensionless_unscaled)
    arrays = tuple(q.view(np.ndarray) for q in qs)
    return (subscripts,) + arrays, kwargs, unit, out


@function_helper
def bincount(x, weights=None, minlength=0):
    from astropy.units import Quantity

    if isinstance(x, Quantity):
        raise NotImplementedError
    return (x, weights.value, minlength), {}, weights.unit, None


@function_helper
def digitize(x, bins, *args, **kwargs):
    arrays, unit = _quantities2arrays(x, bins, unit_from_first=True)
    return arrays + args, kwargs, None, None


def _check_bins(bins, unit):
    from astropy.units import Quantity

    check = _as_quantity(bins)
    if check.ndim > 0:
        return check.to_value(unit)
    elif isinstance(bins, Quantity):
        # bins should be an integer (or at least definitely not a Quantity).
        raise NotImplementedError
    else:
        return bins


def _check_range(range, unit):
    range = _as_quantity(range)
    range = range.to_value(unit)
    return range


@function_helper
def histogram_bin_edges(a, bins=10, range=None, weights=None):
    # weights is currently unused
    a = _as_quantity(a)
    if not isinstance(bins, str):
        bins = _check_bins(bins, a.unit)

    if range is not None:
        range = _check_range(range, a.unit)

    return (a.value, bins, range, weights), {}, a.unit, None


@function_helper
def histogram(a, bins=10, range=None, density=None, weights=None):
    if weights is not None:
        weights = _as_quantity(weights)
        unit = weights.unit
        weights = weights.value
    else:
        unit = None

    a = _as_quantity(a)
    if not isinstance(bins, str):
        bins = _check_bins(bins, a.unit)

    if range is not None:
        range = _check_range(range, a.unit)

    if density:
        unit = (unit or 1) / a.unit

    return (
        (a.value, bins, range),
        {"weights": weights, "density": density},
        (unit, a.unit),
        None,
    )


@function_helper
def histogram2d(x, y, bins=10, range=None, density=None, weights=None):
    from astropy.units import Quantity

    if weights is not None:
        weights = _as_quantity(weights)
        unit = weights.unit
        weights = weights.value
    else:
        unit = None

    x, y = _as_quantities(x, y)
    try:
        n = len(bins)
    except TypeError:
        # bins should be an integer (or at least definitely not a Quantity).
        if isinstance(bins, Quantity):
            raise NotImplementedError

    else:
        if n == 1:
            raise NotImplementedError
        elif n == 2 and not isinstance(bins, Quantity):
            bins = [_check_bins(b, unit) for (b, unit) in zip(bins, (x.unit, y.unit))]
        else:
            bins = _check_bins(bins, x.unit)
            y = y.to(x.unit)

    if range is not None:
        range = tuple(
            _check_range(r, unit) for (r, unit) in zip(range, (x.unit, y.unit))
        )

    if density:
        unit = (unit or 1) / x.unit / y.unit

    return (
        (x.value, y.value, bins, range),
        {"weights": weights, "density": density},
        (unit, x.unit, y.unit),
        None,
    )


@function_helper
def histogramdd(sample, bins=10, range=None, density=None, weights=None):
    if weights is not None:
        weights = _as_quantity(weights)
        unit = weights.unit
        weights = weights.value
    else:
        unit = None

    try:
        # Sample is an ND-array.
        _, D = sample.shape
    except (AttributeError, ValueError):
        # Sample is a sequence of 1D arrays.
        sample = _as_quantities(*sample)
        sample_units = [s.unit for s in sample]
        sample = [s.value for s in sample]
        D = len(sample)
    else:
        sample = _as_quantity(sample)
        sample_units = [sample.unit] * D

    try:
        M = len(bins)
    except TypeError:
        # bins should be an integer
        from astropy.units import Quantity

        if isinstance(bins, Quantity):
            raise NotImplementedError
    else:
        if M != D:
            raise ValueError(
                "The dimension of bins must be equal to the dimension of the  sample x."
            )
        bins = [_check_bins(b, unit) for (b, unit) in zip(bins, sample_units)]

    if range is not None:
        range = tuple(_check_range(r, unit) for (r, unit) in zip(range, sample_units))

    if density:
        unit = functools.reduce(operator.truediv, sample_units, (unit or 1))

    return (
        (sample, bins, range),
        {"weights": weights, "density": density},
        (unit, sample_units),
        None,
    )


@function_helper
def diff(a, n=1, axis=-1, prepend=np._NoValue, append=np._NoValue):
    a = _as_quantity(a)
    if prepend is not np._NoValue:
        prepend = _as_quantity(prepend).to_value(a.unit)
    if append is not np._NoValue:
        append = _as_quantity(append).to_value(a.unit)
    return (a.value, n, axis, prepend, append), {}, a.unit, None


@function_helper
def gradient(f, *varargs, **kwargs):
    f = _as_quantity(f)
    axis = kwargs.get("axis")
    if axis is None:
        n_axis = f.ndim
    elif isinstance(axis, tuple):
        n_axis = len(axis)
    else:
        n_axis = 1

    if varargs:
        varargs = _as_quantities(*varargs)
        if len(varargs) == 1 and n_axis > 1:
            varargs = varargs * n_axis

    if varargs:
        units = [f.unit / q.unit for q in varargs]
        varargs = tuple(q.value for q in varargs)
    else:
        units = [f.unit] * n_axis

    if len(units) == 1:
        units = units[0]

    return (f.value,) + varargs, kwargs, units, None


@function_helper
def logspace(start, stop, *args, **kwargs):
    from astropy.units import LogQuantity, dex

    if not isinstance(start, LogQuantity) or not isinstance(stop, LogQuantity):
        raise NotImplementedError

    # Get unit from end point as for linspace.
    stop = stop.to(dex(stop.unit.physical_unit))
    start = start.to(stop.unit)
    unit = stop.unit.physical_unit
    return (start.value, stop.value) + args, kwargs, unit, None


@function_helper
def geomspace(start, stop, *args, **kwargs):
    # Get unit from end point as for linspace.
    (stop, start), unit = _quantities2arrays(stop, start)
    return (start, stop) + args, kwargs, unit, None


@function_helper
def interp(x, xp, fp, *args, **kwargs):
    from astropy.units import Quantity

    (x, xp), _ = _quantities2arrays(x, xp)
    if isinstance(fp, Quantity):
        unit = fp.unit
        fp = fp.value
    else:
        unit = None

    return (x, xp, fp) + args, kwargs, unit, None


@function_helper
def unique(
    ar,
    return_index=False,
    return_inverse=False,
    return_counts=False,
    axis=None,
    *,
    equal_nan=True,
    **kwargs,
):
    # having **kwargs allows to support sorted (for not NUMPY_LT_2_3) without
    # introducing it pre-maturely in older supported numpy versions
    unit = ar.unit
    n_index = sum(bool(i) for i in (return_index, return_inverse, return_counts))
    if n_index:
        unit = [unit] + n_index * [None]

    return (
        (ar.value, return_index, return_inverse, return_counts, axis),
        kwargs | {"equal_nan": equal_nan},
        unit,
        None,
    )


@function_helper
def intersect1d(ar1, ar2, assume_unique=False, return_indices=False):
    (ar1, ar2), unit = _quantities2arrays(ar1, ar2)
    if return_indices:
        unit = [unit, None, None]
    return (ar1, ar2, assume_unique, return_indices), {}, unit, None


@function_helper(helps=(np.setxor1d, np.union1d, np.setdiff1d))
def twosetop(ar1, ar2, *args, **kwargs):
    (ar1, ar2), unit = _quantities2arrays(ar1, ar2)
    return (ar1, ar2) + args, kwargs, unit, None


@function_helper
def isin(element, test_elements, *args, **kwargs):
    # This tests whether element is in test_elements, so we should change the unit of
    # element to that of test_elements.
    (ar1, ar2), unit = _quantities2arrays(element, test_elements)
    return (ar1, ar2) + args, kwargs, None, None


@function_helper  # np.in1d deprecated in not NUMPY_LT_2_0.
def in1d(ar1, ar2, *args, **kwargs):
    # This tests whether ar1 is in ar2, so we should change the unit of
    # ar1 to that of ar2.
    (ar2, ar1), unit = _quantities2arrays(ar2, ar1)
    return (ar1, ar2) + args, kwargs, None, None


@dispatched_function
def apply_over_axes(func, a, axes):
    # Copied straight from numpy/lib/shape_base, just to omit its
    # val = asarray(a); if only it had been asanyarray, or just not there
    # since a is assumed to an an array in the next line...
    # Which is what we do here - we can only get here if it is a Quantity.
    val = a
    N = a.ndim
    if np.array(axes).ndim == 0:
        axes = (axes,)
    for axis in axes:
        if axis < 0:
            axis = N + axis
        args = (val, axis)
        res = func(*args)
        if res.ndim == val.ndim:
            val = res
        else:
            res = np.expand_dims(res, axis)
            if res.ndim == val.ndim:
                val = res
            else:
                raise ValueError(
                    "function is not returning an array of the correct shape"
                )
    # Returning unit is None to signal nothing should happen to
    # the output.
    return val, None, None


@dispatched_function
def array_repr(arr, *args, **kwargs):
    # TODO: The addition of "unit='...'" doesn't worry about line
    # length.  Could copy & adapt _array_repr_implementation from
    # numpy.core.arrayprint.py
    cls_name = arr.__class__.__name__
    fake_name = "_" * len(cls_name)
    fake_cls = type(fake_name, (np.ndarray,), {})
    no_unit = np.array_repr(arr.view(fake_cls), *args, **kwargs).replace(
        fake_name, cls_name
    )
    unit_part = f"unit='{arr.unit}'"
    pre, dtype, post = no_unit.rpartition("dtype")
    if dtype:
        return f"{pre}{unit_part}, {dtype}{post}", None, None
    else:
        return f"{no_unit[:-1]}, {unit_part})", None, None


@dispatched_function
def array_str(a, *args, **kwargs):
    # TODO: The addition of the unit doesn't worry about line length.
    # Could copy & adapt _array_repr_implementation from
    # numpy.core.arrayprint.py
    no_unit = np.array_str(a.value, *args, **kwargs)
    return no_unit + a._unitstr, None, None


@function_helper
def array2string(a, *args, **kwargs):
    # array2string breaks on quantities as it tries to turn individual
    # items into float, which works only for dimensionless.  Since the
    # defaults would not keep any unit anyway, this is rather pointless -
    # we're better off just passing on the array view.  However, one can
    # also work around this by passing on a formatter (as is done in Angle).
    # So, we do nothing if the formatter argument is present and has the
    # relevant formatter for our dtype.
    formatter = args[6] if len(args) >= 7 else kwargs.get("formatter")

    if formatter is None:
        a = a.value
    else:
        # See whether it covers our dtype.
        if NUMPY_LT_2_0:
            from numpy.core.arrayprint import _get_format_function, _make_options_dict
        else:
            from numpy._core.arrayprint import _get_format_function, _make_options_dict

        with np.printoptions(formatter=formatter) as options:
            options = _make_options_dict(**options)
            try:
                ff = _get_format_function(a.value, **options)
            except Exception:
                # Shouldn't happen, but possibly we're just not being smart
                # enough, so let's pass things on as is.
                pass
            else:
                # If the selected format function is that of numpy, we know
                # things will fail if we pass in the Quantity, so use .value.
                if "numpy" in ff.__module__:
                    a = a.value

    return (a,) + args, kwargs, None, None


@function_helper
def diag(v, *args, **kwargs):
    # Function works for *getting* the diagonal, but not *setting*.
    # So, override always.
    return (v.value,) + args, kwargs, v.unit, None


@function_helper(module=np.linalg)
def svd(a, full_matrices=True, compute_uv=True, hermitian=False):
    unit = a.unit
    if compute_uv:
        unit = (None, unit, None)

    return ((a.view(np.ndarray), full_matrices, compute_uv, hermitian), {}, unit, None)


def _interpret_tol(tol, unit):
    from astropy.units import Quantity

    return Quantity(tol, unit).value


@function_helper(module=np.linalg)
def matrix_rank(A, tol=None, *args, **kwargs):
    if tol is not None:
        tol = _interpret_tol(tol, A.unit)

    return (A.view(np.ndarray), tol) + args, kwargs, None, None


@function_helper(helps={np.linalg.inv, np.linalg.tensorinv})
def inv(a, *args, **kwargs):
    return (a.view(np.ndarray),) + args, kwargs, 1 / a.unit, None


if NUMPY_LT_2_0:

    @function_helper(module=np.linalg)
    def pinv(a, rcond=1e-15, *args, **kwargs):
        rcond = _interpret_tol(rcond, a.unit)

        return (a.view(np.ndarray), rcond) + args, kwargs, 1 / a.unit, None

else:

    @function_helper(module=np.linalg)
    def pinv(a, rcond=None, hermitian=False, *, rtol=np._NoValue):
        if rcond is not None:
            rcond = _interpret_tol(rcond, a.unit)
        if rtol is not np._NoValue and rtol is not None:
            rtol = _interpret_tol(rtol, a.unit)

        return (
            (a.view(np.ndarray),),
            dict(rcond=rcond, hermitian=hermitian, rtol=rtol),
            1 / a.unit,
            None,
        )


@function_helper(module=np.linalg)
def det(a):
    return (a.view(np.ndarray),), {}, a.unit ** a.shape[-1], None


@function_helper(helps={np.linalg.solve, np.linalg.tensorsolve})
def solve(a, b, *args, **kwargs):
    a, b = _as_quantities(a, b)

    return (
        (a.view(np.ndarray), b.view(np.ndarray)) + args,
        kwargs,
        b.unit / a.unit,
        None,
    )


@function_helper(module=np.linalg)
def lstsq(a, b, rcond="warn" if NUMPY_LT_2_0 else None):
    a, b = _as_quantities(a, b)

    if rcond not in (None, "warn", -1):
        rcond = _interpret_tol(rcond, a.unit)

    return (
        (a.view(np.ndarray), b.view(np.ndarray), rcond),
        {},
        (b.unit / a.unit, b.unit**2, None, a.unit),
        None,
    )


@function_helper(module=np.linalg)
def norm(x, ord=None, *args, **kwargs):
    if ord == 0:
        from astropy.units import dimensionless_unscaled

        unit = dimensionless_unscaled
    else:
        unit = x.unit
    return (x.view(np.ndarray), ord) + args, kwargs, unit, None


@function_helper(module=np.linalg)
def matrix_power(a, n):
    return (a.value, n), {}, a.unit**n, None


if NUMPY_LT_2_0:

    @function_helper(module=np.linalg)
    def cholesky(a):
        return (a.value,), {}, a.unit**0.5, None

else:

    @function_helper(module=np.linalg)
    def cholesky(a, /, *, upper=False):
        return (a.value,), {"upper": upper}, a.unit**0.5, None


@function_helper(module=np.linalg)
def qr(a, mode="reduced"):
    if mode.startswith("e"):
        units = None
    elif mode == "r":
        units = a.unit
    else:
        from astropy.units import dimensionless_unscaled

        units = (dimensionless_unscaled, a.unit)

    return (a.value, mode), {}, units, None


@function_helper(helps={np.linalg.eig, np.linalg.eigh})
def eig(a, *args, **kwargs):
    from astropy.units import dimensionless_unscaled

    return (a.value,) + args, kwargs, (a.unit, dimensionless_unscaled), None


if not NUMPY_LT_2_0:
    # these functions were added in numpy 2.0

    @function_helper(module=np.linalg)
    def outer(x1, x2, /):
        # maybe this one can be marked as subclass-safe in the near future ?
        # see https://github.com/numpy/numpy/pull/25101#discussion_r1419879122
        x1, x2 = _as_quantities(x1, x2)
        return (x1.view(np.ndarray), x2.view(np.ndarray)), {}, x1.unit * x2.unit, None


# ======================= np.lib.recfunctions =======================


@function_helper(module=np.lib.recfunctions)
def structured_to_unstructured(arr, *args, **kwargs):
    """
    Convert a structured quantity to an unstructured one.
    This only works if all the units are compatible.

    """
    from astropy.units import StructuredUnit

    target_unit = arr.unit.values()[0]

    def replace_unit(x):
        if isinstance(x, StructuredUnit):
            return x._recursively_apply(replace_unit)
        else:
            return target_unit

    to_unit = arr.unit._recursively_apply(replace_unit)
    return (arr.to_value(to_unit),) + args, kwargs, target_unit, None


def _build_structured_unit(dtype, unit):
    """Build structured unit from dtype.

    Parameters
    ----------
    dtype : `numpy.dtype`
    unit : `astropy.units.Unit`

    Returns
    -------
    `astropy.units.Unit` or tuple
    """
    if dtype.fields is None:
        return unit

    return tuple(_build_structured_unit(v[0], unit) for v in dtype.fields.values())


@function_helper(module=np.lib.recfunctions)
def unstructured_to_structured(arr, dtype=None, *args, **kwargs):
    from astropy.units import StructuredUnit

    target_unit = StructuredUnit(_build_structured_unit(dtype, arr.unit))

    return (arr.to_value(arr.unit), dtype) + args, kwargs, target_unit, None


def _izip_units_flat(iterable):
    """Returns an iterator of collapsing any nested unit structure.

    Parameters
    ----------
    iterable : Iterable[StructuredUnit | Unit] or StructuredUnit
        A structured unit or iterable thereof.

    Yields
    ------
    unit
    """
    from astropy.units import StructuredUnit

    # Make Structured unit (pass-through if it is already).
    units = StructuredUnit(iterable)

    # Yield from structured unit.
    for v in units.values():
        if isinstance(v, StructuredUnit):
            yield from _izip_units_flat(v)
        else:
            yield v


@function_helper(helps=rfn.merge_arrays)
def merge_arrays(
    seqarrays,
    fill_value=-1,
    flatten=False,
    usemask=False,
    asrecarray=False,
):
    """Merge structured Quantities field by field.

    Like :func:`numpy.lib.recfunctions.merge_arrays`. Note that ``usemask`` and
    ``asrecarray`` are not supported at this time and will raise a ValueError if
    not `False`.
    """
    from astropy.units import Quantity, StructuredUnit

    if asrecarray:
        # TODO? implement if Quantity ever supports rec.array
        raise ValueError("asrecarray=True is not supported.")
    if usemask:
        # TODO: use MaskedQuantity for this case
        raise ValueError("usemask=True is not supported.")

    # Do we have a single Quantity as input?
    if isinstance(seqarrays, Quantity):
        seqarrays = (seqarrays,)

    # Note: this also converts ndarray -> Quantity[dimensionless]
    seqarrays = _as_quantities(*seqarrays)
    arrays = tuple(q.value for q in seqarrays)
    units = tuple(q.unit for q in seqarrays)

    if flatten:
        unit = StructuredUnit(tuple(_izip_units_flat(units)))
    elif len(arrays) == 1:
        unit = StructuredUnit(units[0])
    else:
        unit = StructuredUnit(units)

    return (
        (arrays,),
        dict(
            fill_value=fill_value,
            flatten=flatten,
            usemask=usemask,
            asrecarray=asrecarray,
        ),
        unit,
        None,
    )
