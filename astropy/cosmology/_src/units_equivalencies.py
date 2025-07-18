# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""Cosmological unit equivalencies."""

__all__ = [
    # redshift equivalencies
    "dimensionless_redshift",
    "redshift_distance",
    "redshift_hubble",
    "redshift_temperature",
    # other equivalencies
    "with_H0",
    "with_redshift",
]


import sys
from typing import TYPE_CHECKING, Any, Literal, TypeAlias, Union

import astropy.units as u
from astropy.cosmology._src.funcs.optimize import _ZAtValueKWArgs

from .default import default_cosmology
from .funcs.optimize import z_at_value
from .units import littleh, redshift

if TYPE_CHECKING:
    import astropy.cosmology

if sys.version_info < (3, 12):
    _UnpackZAtValueKWArgs = Any
else:
    from typing import Unpack

    _UnpackZAtValueKWArgs: TypeAlias = Unpack[_ZAtValueKWArgs]


__doctest_requires__ = {("with_redshift", "redshift_distance"): ["scipy"]}


def dimensionless_redshift() -> u.Equivalency:
    """Allow redshift to be 1-to-1 equivalent to dimensionless.

    It is special compared to other equivalency pairs in that it allows
    this independent of the power to which the redshift is raised, and
    independent of whether it is part of a more complicated unit. It is
    similar to u.dimensionless_angles() in this respect.
    """
    return u.Equivalency([(redshift, None)], "dimensionless_redshift")


def redshift_distance(
    cosmology: Union["astropy.cosmology.Cosmology", str, None] = None,
    kind: Literal["comoving", "lookback", "luminosity"] = "comoving",
    **atzkw: _UnpackZAtValueKWArgs,
) -> u.Equivalency:
    """Convert quantities between redshift and distance.

    Care should be taken to not misinterpret a relativistic, gravitational, etc
    redshift as a cosmological one.

    Parameters
    ----------
    cosmology : `~astropy.cosmology.Cosmology`, str, or None, optional
        A cosmology realization or built-in cosmology's name (e.g. 'Planck18').
        If None, will use the default cosmology
        (controlled by |default_cosmology|).
    kind : {'comoving', 'lookback', 'luminosity'}, optional
        The distance type for the Equivalency.
        Note this does NOT include the angular diameter distance as this
        distance measure is not monotonic.
    **atzkw
        keyword arguments for :func:`~astropy.cosmology.z_at_value`, which is used to
        convert distance to redshift.

    Returns
    -------
    `~astropy.units.equivalencies.Equivalency`
        Equivalency between redshift and temperature.

    Raises
    ------
    `~astropy.cosmology.CosmologyError`
        If the distance corresponds to a redshift that is larger than ``zmax``.
    Exception
        See :func:`~astropy.cosmology.z_at_value` for possible exceptions, e.g. if the
        distance maps to a redshift that is larger than ``zmax``, the maximum redshift.

    Examples
    --------
    >>> import astropy.units as u
    >>> import astropy.cosmology.units as cu
    >>> from astropy.cosmology import WMAP9

    >>> z = 1100 * cu.redshift
    >>> d = z.to(u.Mpc, cu.redshift_distance(WMAP9, kind="comoving"))
    >>> d  # doctest: +FLOAT_CMP
    <Quantity 14004.03157418 Mpc>

    The reverse operation is also possible, though not always as simple. To convert a
    very large distance to a redshift it might be necessary to specify a large enough
    ``zmax`` value. See :func:`~astropy.cosmology.z_at_value` for details.

    >>> d.to(cu.redshift, cu.redshift_distance(WMAP9, kind="comoving", zmax=1200))  # doctest: +FLOAT_CMP
    <Quantity 1100.000 redshift>
    """
    # get cosmology: None -> default and process str / class
    cosmology = cosmology if cosmology is not None else default_cosmology.get()
    with default_cosmology.set(cosmology):  # if already cosmo, passes through
        cosmology = default_cosmology.get()

    allowed_kinds = ("comoving", "lookback", "luminosity")
    if kind not in allowed_kinds:
        raise ValueError(f"`kind` is not one of {allowed_kinds}")

    method = getattr(cosmology, kind + "_distance")

    def z_to_distance(z):
        """Redshift to distance."""
        return method(z)

    def distance_to_z(d):
        """Distance to redshift."""
        return z_at_value(method, d << u.Mpc, **atzkw)

    return u.Equivalency(
        [(redshift, u.Mpc, z_to_distance, distance_to_z)],
        "redshift_distance",
        {"cosmology": cosmology, "distance": kind},
    )


def redshift_hubble(
    cosmology: Union["astropy.cosmology.Cosmology", str, None] = None,
    **atzkw: _UnpackZAtValueKWArgs,
) -> u.Equivalency:
    """Convert quantities between redshift and Hubble parameter and little-h.

    Care should be taken to not misinterpret a relativistic, gravitational, etc
    redshift as a cosmological one.

    Parameters
    ----------
    cosmology : `~astropy.cosmology.Cosmology`, str, or None, optional
        A cosmology realization or built-in cosmology's name (e.g. 'Planck18').
        If None, will use the default cosmology
        (controlled by |default_cosmology|).
    **atzkw
        keyword arguments for :func:`~astropy.cosmology.z_at_value`

    Returns
    -------
    `~astropy.units.equivalencies.Equivalency`
        Equivalency between redshift and Hubble parameter and little-h unit.

    Examples
    --------
    >>> import astropy.units as u
    >>> import astropy.cosmology.units as cu
    >>> from astropy.cosmology import WMAP9

    >>> z = 1100 * cu.redshift
    >>> equivalency = cu.redshift_hubble(WMAP9)  # construct equivalency

    >>> z.to(u.km / u.s / u.Mpc, equivalency)  # doctest: +FLOAT_CMP
    <Quantity 1565637.40154275 km / (Mpc s)>

    >>> z.to(cu.littleh, equivalency)  # doctest: +FLOAT_CMP
    <Quantity 15656.37401543 littleh>
    """
    # get cosmology: None -> default and process str / class
    cosmology = cosmology if cosmology is not None else default_cosmology.get()
    with default_cosmology.set(cosmology):  # if already cosmo, passes through
        cosmology = default_cosmology.get()

    def z_to_hubble(z):
        """Redshift to Hubble parameter."""
        return cosmology.H(z)

    def hubble_to_z(H):
        """Hubble parameter to redshift."""
        return z_at_value(cosmology.H, H << (u.km / u.s / u.Mpc), **atzkw)

    def z_to_littleh(z):
        """Redshift to :math:`h`-unit Quantity."""
        return z_to_hubble(z).to_value(u.km / u.s / u.Mpc) / 100 * littleh

    def littleh_to_z(h):
        """:math:`h`-unit Quantity to redshift."""
        return hubble_to_z(h * 100)

    return u.Equivalency(
        [
            (redshift, u.km / u.s / u.Mpc, z_to_hubble, hubble_to_z),
            (redshift, littleh, z_to_littleh, littleh_to_z),
        ],
        "redshift_hubble",
        {"cosmology": cosmology},
    )


def redshift_temperature(
    cosmology: Union["astropy.cosmology.Cosmology", str, None] = None,
    **atzkw: _UnpackZAtValueKWArgs,
) -> u.Equivalency:
    """Convert quantities between redshift and CMB temperature.

    Care should be taken to not misinterpret a relativistic, gravitational, etc
    redshift as a cosmological one.

    Parameters
    ----------
    cosmology : `~astropy.cosmology.Cosmology`, str, or None, optional
        A cosmology realization or built-in cosmology's name (e.g. 'Planck18').
        If None, will use the default cosmology
        (controlled by |default_cosmology|).
    **atzkw
        keyword arguments for :func:`~astropy.cosmology.z_at_value`

    Returns
    -------
    `~astropy.units.equivalencies.Equivalency`
        Equivalency between redshift and temperature.

    Examples
    --------
    >>> import astropy.units as u
    >>> import astropy.cosmology.units as cu
    >>> from astropy.cosmology import WMAP9

    >>> z = 1100 * cu.redshift
    >>> z.to(u.K, cu.redshift_temperature(WMAP9))
    <Quantity 3000.225 K>
    """
    # get cosmology: None -> default and process str / class
    cosmology = cosmology if cosmology is not None else default_cosmology.get()
    with default_cosmology.set(cosmology):  # if already cosmo, passes through
        cosmology = default_cosmology.get()

    def z_to_Tcmb(z):
        return cosmology.Tcmb(z)

    def Tcmb_to_z(T):
        return z_at_value(cosmology.Tcmb, T << u.K, **atzkw)

    return u.Equivalency(
        [(redshift, u.K, z_to_Tcmb, Tcmb_to_z)],
        "redshift_temperature",
        {"cosmology": cosmology},
    )


def with_redshift(
    cosmology: Union["astropy.cosmology.Cosmology", str, None] = None,
    *,
    distance: Literal["comoving", "lookback", "luminosity"] = "comoving",
    hubble: bool = True,
    Tcmb: bool = True,
    atzkw: _ZAtValueKWArgs | None = None,
) -> u.Equivalency:
    """Convert quantities between measures of cosmological distance.

    Note: by default all equivalencies are on and must be explicitly turned off.
    Care should be taken to not misinterpret a relativistic, gravitational, etc
    redshift as a cosmological one.

    Parameters
    ----------
    cosmology : `~astropy.cosmology.Cosmology`, str, or None, optional
        A cosmology realization or built-in cosmology's name (e.g. 'Planck18').
        If `None`, will use the default cosmology
        (controlled by |default_cosmology|).

    distance : {'comoving', 'lookback', 'luminosity'} or None (optional, keyword-only)
        The type of distance equivalency to create or `None`.
        Default is 'comoving'.
    hubble : bool (optional, keyword-only)
        Whether to create a Hubble parameter <-> redshift equivalency, using
        ``Cosmology.H``. Default is `True`.
    Tcmb : bool (optional, keyword-only)
        Whether to create a CMB temperature <-> redshift equivalency, using
        ``Cosmology.Tcmb``. Default is `True`.

    atzkw : dict or None (optional, keyword-only)
        keyword arguments for :func:`~astropy.cosmology.z_at_value`

    Returns
    -------
    `~astropy.units.equivalencies.Equivalency`
        With equivalencies between redshift and distance / Hubble / temperature.

    Examples
    --------
    >>> import astropy.units as u
    >>> import astropy.cosmology.units as cu
    >>> from astropy.cosmology import WMAP9

    >>> equivalency = cu.with_redshift(WMAP9)
    >>> z = 1100 * cu.redshift

    Redshift to (comoving) distance:

    >>> z.to(u.Mpc, equivalency)  # doctest: +FLOAT_CMP
    <Quantity 14004.03157418 Mpc>

    Redshift to the Hubble parameter:

    >>> z.to(u.km / u.s / u.Mpc, equivalency)  # doctest: +FLOAT_CMP
    <Quantity 1565637.40154275 km / (Mpc s)>

    >>> z.to(cu.littleh, equivalency)  # doctest: +FLOAT_CMP
    <Quantity 15656.37401543 littleh>

    Redshift to CMB temperature:

    >>> z.to(u.K, equivalency)
    <Quantity 3000.225 K>
    """
    # get cosmology: None -> default and process str / class
    cosmology = cosmology if cosmology is not None else default_cosmology.get()
    with default_cosmology.set(cosmology):  # if already cosmo, passes through
        cosmology = default_cosmology.get()

    atzkw = atzkw if atzkw is not None else {}
    equivs: list[u.Equivalency] = []  # will append as built

    # Hubble <-> Redshift
    if hubble:
        equivs.extend(redshift_hubble(cosmology, **atzkw))

    # CMB Temperature <-> Redshift
    if Tcmb:
        equivs.extend(redshift_temperature(cosmology, **atzkw))

    # Distance <-> Redshift, but need to choose which distance
    if distance is not None:
        equivs.extend(redshift_distance(cosmology, kind=distance, **atzkw))

    # -----------
    return u.Equivalency(
        equivs,
        "with_redshift",
        {"cosmology": cosmology, "distance": distance, "hubble": hubble, "Tcmb": Tcmb},
    )


# ===================================================================


def with_H0(H0: u.Quantity | None = None) -> u.Equivalency:
    """Convert between quantities with little-h and the equivalent physical units.

    Parameters
    ----------
    H0 : None or Quantity ['frequency']
        The value of the Hubble constant to assume. If a |Quantity|, will assume the
        quantity *is* ``H0``. If `None` (default), use the ``H0`` attribute from
        |default_cosmology|.

    References
    ----------
    For an illuminating discussion on why you may or may not want to use
    little-h at all, see https://arxiv.org/pdf/1308.4150.pdf
    """
    if H0 is None:
        H0 = default_cosmology.get().H0

    h100_val_unit = u.Unit(100 / (H0.to_value((u.km / u.s) / u.Mpc)) * littleh)

    return u.Equivalency([(h100_val_unit, None)], "with_H0", kwargs={"H0": H0})
