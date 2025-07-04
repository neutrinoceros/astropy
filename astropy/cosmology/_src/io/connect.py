# Licensed under a 3-clause BSD style license - see LICENSE.rst

__all__ = [
    # classes
    "CosmologyFromFormat",
    "CosmologyRead",
    "CosmologyToFormat",
    "CosmologyWrite",
]

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Literal, TypeVar, overload

from astropy.cosmology._src.typing import _CosmoT
from astropy.io import registry as io_registry
from astropy.table import Row, Table
from astropy.units import add_enabled_units

# isort: split
import astropy.cosmology._src.units as cu

if TYPE_CHECKING:
    import astropy.cosmology


__doctest_skip__ = __all__


# NOTE: private b/c RTD error
_MT = TypeVar("_MT", bound=Mapping)  # type: ignore[type-arg]


# ==============================================================================
# Read / Write

readwrite_registry = io_registry.UnifiedIORegistry()


class CosmologyRead(io_registry.UnifiedReadWrite):
    """Read and parse data to a `~astropy.cosmology.Cosmology`.

    This function provides the Cosmology interface to the Astropy unified I/O
    layer. This allows easily reading a file in supported data formats using
    syntax such as::

        >>> from astropy.cosmology import Cosmology
        >>> cosmo1 = Cosmology.read('<file name>')

    When the ``read`` method is called from a subclass the subclass will
    provide a keyword argument ``cosmology=<class>`` to the registered read
    method. The method uses this cosmology class, regardless of the class
    indicated in the file, and sets parameters' default values from the class'
    signature.

    Get help on the available readers using the ``help()`` method::

      >>> Cosmology.read.help()  # Get help reading and list supported formats
      >>> Cosmology.read.help(format='<format>')  # Get detailed help on a format
      >>> Cosmology.read.list_formats()  # Print list of available formats

    See also: https://docs.astropy.org/en/stable/io/unified.html

    Parameters
    ----------
    *args
        Positional arguments passed through to data reader. If supplied the
        first argument is typically the input filename.
    format : str (optional, keyword-only)
        File format specifier.
    **kwargs
        Keyword arguments passed through to data reader.

    Returns
    -------
    out : `~astropy.cosmology.Cosmology` subclass instance
        `~astropy.cosmology.Cosmology` corresponding to file contents.

    Notes
    -----
    """

    def __init__(
        self,
        instance: "astropy.cosmology.Cosmology",
        cosmo_cls: type["astropy.cosmology.Cosmology"],
    ) -> None:
        super().__init__(instance, cosmo_cls, "read", registry=readwrite_registry)

    def __call__(self, *args: Any, **kwargs: Any) -> "astropy.cosmology.Cosmology":
        from astropy.cosmology._src.core import Cosmology

        # so subclasses can override, also pass the class as a kwarg.
        # allows for `FlatLambdaCDM.read` and
        # `Cosmology.read(..., cosmology=FlatLambdaCDM)`
        if self._cls is not Cosmology:
            kwargs.setdefault("cosmology", self._cls)  # set, if not present
            # check that it is the correct cosmology, can be wrong if user
            # passes in e.g. `w0wzCDM.read(..., cosmology=FlatLambdaCDM)`
            valid = (self._cls, self._cls.__qualname__)
            if kwargs["cosmology"] not in valid:
                raise ValueError(
                    "keyword argument `cosmology` must be either the class "
                    f"{valid[0]} or its qualified name '{valid[1]}'"
                )

        with add_enabled_units(cu):
            return self.registry.read(self._cls, *args, **kwargs)


class CosmologyWrite(io_registry.UnifiedReadWrite):
    """Write this Cosmology object out in the specified format.

    This function provides the Cosmology interface to the astropy unified I/O
    layer. This allows easily writing a file in supported data formats
    using syntax such as::

      >>> from astropy.cosmology import Planck18
      >>> Planck18.write('<file name>')

    Get help on the available writers for ``Cosmology`` using the ``help()``
    method::

      >>> Cosmology.write.help()  # Get help writing and list supported formats
      >>> Cosmology.write.help(format='<format>')  # Get detailed help on format
      >>> Cosmology.write.list_formats()  # Print list of available formats

    Parameters
    ----------
    *args
        Positional arguments passed through to data writer. If supplied the
        first argument is the output filename.
    format : str (optional, keyword-only)
        File format specifier.
    **kwargs
        Keyword arguments passed through to data writer.

    Notes
    -----
    """

    def __init__(
        self,
        instance: "astropy.cosmology.Cosmology",
        cls: type["astropy.cosmology.Cosmology"],
    ) -> None:
        super().__init__(instance, cls, "write", registry=readwrite_registry)

    def __call__(self, *args: Any, **kwargs: Any) -> None:
        self.registry.write(self._instance, *args, **kwargs)


# ==============================================================================
# Format Interchange
# for transforming instances, e.g. Cosmology <-> dict

convert_registry = io_registry.UnifiedIORegistry()


class CosmologyFromFormat(io_registry.UnifiedReadWrite):
    """Transform object to a `~astropy.cosmology.Cosmology`.

    This function provides the Cosmology interface to the Astropy unified I/O
    layer. This allows easily parsing supported data formats using
    syntax such as::

      >>> from astropy.cosmology import Cosmology
      >>> cosmo1 = Cosmology.from_format(cosmo_mapping, format='mapping')

    When the ``from_format`` method is called from a subclass the subclass will
    provide a keyword argument ``cosmology=<class>`` to the registered parser.
    The method uses this cosmology class, regardless of the class indicated in
    the data, and sets parameters' default values from the class' signature.

    Get help on the available readers using the ``help()`` method::

      >>> Cosmology.from_format.help()  # Get help and list supported formats
      >>> Cosmology.from_format.help('<format>')  # Get detailed help on a format
      >>> Cosmology.from_format.list_formats()  # Print list of available formats

    See also: https://docs.astropy.org/en/stable/io/unified.html

    Parameters
    ----------
    obj : object
        The object to parse according to 'format'
    *args
        Positional arguments passed through to data parser.
    format : str or None, optional keyword-only
        Object format specifier. For `None` (default) CosmologyFromFormat tries
        to identify the correct format.
    **kwargs
        Keyword arguments passed through to data parser.
        Parsers should accept the following keyword arguments:

        - cosmology : the class (or string name thereof) to use / check when
                      constructing the cosmology instance.

    Returns
    -------
    out : `~astropy.cosmology.Cosmology` subclass instance
        `~astropy.cosmology.Cosmology` corresponding to ``obj`` contents.
    """

    def __init__(
        self,
        instance: "astropy.cosmology.Cosmology",
        cosmo_cls: type["astropy.cosmology.Cosmology"],
    ) -> None:
        super().__init__(instance, cosmo_cls, "read", registry=convert_registry)

    # ===============================================================
    # __call__ overloads
    # note: format: ... | None means the format can be auto-detected from the input.

    @overload
    def __call__(
        self,
        obj: _CosmoT,
        *args: Any,
        format: Literal["astropy.cosmology"] | None,
        **kwargs: Any,
    ) -> _CosmoT: ...

    @overload
    def __call__(
        self,
        obj: "astropy.cosmology._src.io.builtin.model._CosmologyModel",
        *args: Any,
        format: Literal["astropy.model"] | None,
        **kwargs: Any,
    ) -> "astropy.cosmology.Cosmology": ...

    @overload
    def __call__(
        self, obj: Row, *args: Any, format: Literal["astropy.row"] | None, **kwargs: Any
    ) -> "astropy.cosmology.Cosmology": ...

    @overload
    def __call__(
        self,
        obj: Table,
        *args: Any,
        format: Literal["astropy.table"] | None,
        **kwargs: Any,
    ) -> "astropy.cosmology.Cosmology": ...

    @overload
    def __call__(
        self,
        obj: Mapping[str, Any],
        *args: Any,
        format: Literal["mapping"] | None,
        **kwargs: Any,
    ) -> "astropy.cosmology.Cosmology": ...

    @overload
    def __call__(
        self, obj: str, *args: Any, format: Literal["yaml"], **kwargs: Any
    ) -> "astropy.cosmology.Cosmology": ...

    @overload
    def __call__(
        self, obj: Any, *args: Any, format: str | None = None, **kwargs: Any
    ) -> "astropy.cosmology.Cosmology": ...

    def __call__(
        self, obj: Any, *args: Any, format: str | None = None, **kwargs: Any
    ) -> "astropy.cosmology.Cosmology":
        from astropy.cosmology._src.core import Cosmology

        # so subclasses can override, also pass the class as a kwarg.
        # allows for `FlatLambdaCDM.read` and
        # `Cosmology.read(..., cosmology=FlatLambdaCDM)`
        if self._cls is not Cosmology:
            kwargs.setdefault("cosmology", self._cls)  # set, if not present
            # check that it is the correct cosmology, can be wrong if user
            # passes in e.g. `w0wzCDM.read(..., cosmology=FlatLambdaCDM)`
            valid = (self._cls, self._cls.__qualname__)
            if kwargs["cosmology"] not in valid:
                raise ValueError(
                    "keyword argument `cosmology` must be either the class "
                    f"{valid[0]} or its qualified name '{valid[1]}'"
                )

        with add_enabled_units(cu):
            return self.registry.read(self._cls, obj, *args, format=format, **kwargs)


class CosmologyToFormat(io_registry.UnifiedReadWrite):
    """Transform this Cosmology to another format.

    This function provides the Cosmology interface to the astropy unified I/O
    layer. This allows easily transforming to supported data formats
    using syntax such as::

      >>> from astropy.cosmology import Planck18
      >>> Planck18.to_format("mapping")
      {'cosmology': astropy.cosmology.core.FlatLambdaCDM,
       'name': 'Planck18',
       'H0': <Quantity 67.66 km / (Mpc s)>,
       'Om0': 0.30966,
       ...

    Get help on the available representations for ``Cosmology`` using the
    ``help()`` method::

      >>> Cosmology.to_format.help()  # Get help and list supported formats
      >>> Cosmology.to_format.help('<format>')  # Get detailed help on format
      >>> Cosmology.to_format.list_formats()  # Print list of available formats

    Parameters
    ----------
    format : str
        Format specifier.
    *args
        Positional arguments passed through to data writer. If supplied the
        first argument is the output filename.
    **kwargs
        Keyword arguments passed through to data writer.
    """

    def __init__(
        self,
        instance: "astropy.cosmology.Cosmology",
        cls: type["astropy.cosmology.Cosmology"],
    ) -> None:
        super().__init__(instance, cls, "write", registry=convert_registry)

    # ===============================================================
    # __call__ overloads

    @overload
    def __call__(
        self, format: Literal["astropy.cosmology"], *args: Any, **kwargs: Any
    ) -> "astropy.cosmology.Cosmology": ...

    @overload
    def __call__(
        self, format: Literal["astropy.model"], *args: Any, **kwargs: Any
    ) -> "astropy.cosmology._src.io.builtin.model._CosmologyModel": ...

    @overload
    def __call__(
        self, format: Literal["astropy.row"], *args: Any, **kwargs: Any
    ) -> Row: ...

    @overload
    def __call__(
        self, format: Literal["astropy.table"], *args: Any, **kwargs: Any
    ) -> Table: ...

    @overload  # specific mapping option, where the mapping class is specified.
    def __call__(
        self, format: Literal["mapping"], *args: Any, cls: _MT, **kwargs: Any
    ) -> _MT: ...

    @overload
    def __call__(
        self, format: Literal["mapping"], *args: Any, **kwargs: Any
    ) -> dict[str, Any]: ...

    @overload
    def __call__(self, format: Literal["yaml"], *args: Any, **kwargs: Any) -> str: ...

    @overload
    def __call__(self, format: str, *args: Any, **kwargs: Any) -> Any: ...

    def __call__(self, format: str, *args: Any, **kwargs: Any) -> Any:
        return self.registry.write(self._instance, None, *args, format=format, **kwargs)
