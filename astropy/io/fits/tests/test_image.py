# Licensed under a 3-clause BSD style license - see PYFITS.rst

import math
import os
import time

import numpy as np
import pytest
from numpy.testing import assert_equal

from astropy.io import fits
from astropy.utils.data import get_pkg_data_filename
from astropy.utils.exceptions import AstropyUserWarning

from .conftest import FitsTestCase


class TestImageFunctions(FitsTestCase):
    def test_constructor_name_arg(self):
        """Like the test of the same name in test_table.py"""

        hdu = fits.ImageHDU()
        assert hdu.name == ""
        assert "EXTNAME" not in hdu.header
        hdu.name = "FOO"
        assert hdu.name == "FOO"
        assert hdu.header["EXTNAME"] == "FOO"

        # Passing name to constructor
        hdu = fits.ImageHDU(name="FOO")
        assert hdu.name == "FOO"
        assert hdu.header["EXTNAME"] == "FOO"

        # And overriding a header with a different extname
        hdr = fits.Header()
        hdr["EXTNAME"] = "EVENTS"
        hdu = fits.ImageHDU(header=hdr, name="FOO")
        assert hdu.name == "FOO"
        assert hdu.header["EXTNAME"] == "FOO"

    def test_constructor_ver_arg(self):
        def assert_ver_is(hdu, reference_ver):
            __tracebackhide__ = True
            assert hdu.ver == reference_ver
            assert hdu.header["EXTVER"] == reference_ver

        hdu = fits.ImageHDU()
        assert hdu.ver == 1  # defaults to 1
        assert "EXTVER" not in hdu.header

        hdu.ver = 1
        assert_ver_is(hdu, 1)

        # Passing name to constructor
        hdu = fits.ImageHDU(ver=2)
        assert_ver_is(hdu, 2)

        # And overriding a header with a different extver
        hdr = fits.Header()
        hdr["EXTVER"] = 3
        hdu = fits.ImageHDU(header=hdr, ver=4)
        assert_ver_is(hdu, 4)

        # The header card is not overridden if ver is None or not passed in
        hdr = fits.Header()
        hdr["EXTVER"] = 5
        hdu = fits.ImageHDU(header=hdr, ver=None)
        assert_ver_is(hdu, 5)
        hdu = fits.ImageHDU(header=hdr)
        assert_ver_is(hdu, 5)

    def test_constructor_copies_header(self):
        """
        Regression test for https://aeon.stsci.edu/ssb/trac/pyfits/ticket/153

        Ensure that a header from one HDU is copied when used to initialize new
        HDU.
        """

        ifd = fits.HDUList(fits.PrimaryHDU())
        phdr = ifd[0].header
        phdr["FILENAME"] = "labq01i3q_rawtag.fits"

        primary_hdu = fits.PrimaryHDU(header=phdr)
        ofd = fits.HDUList(primary_hdu)
        ofd[0].header["FILENAME"] = "labq01i3q_flt.fits"

        # Original header should be unchanged
        assert phdr["FILENAME"] == "labq01i3q_rawtag.fits"

    def test_open(self):
        # The function "open" reads a FITS file into an HDUList object.  There
        # are three modes to open: "readonly" (the default), "append", and
        # "update".

        # Open a file read-only (the default mode), the content of the FITS
        # file are read into memory.
        r = fits.open(self.data("test0.fits"))  # readonly

        # data parts are latent instantiation, so if we close the HDUList
        # without touching data, data can not be accessed.
        r.close()

        with pytest.raises(IndexError) as exc_info:
            r[1].data[:2, :2]

        # Check that the exception message is the enhanced version, not the
        # default message from list.__getitem__
        assert str(exc_info.value) == (
            "HDU not found, possibly because the index "
            "is out of range, or because the file was "
            "closed before all HDUs were read"
        )

    def test_open_2(self):
        r = fits.open(self.data("test0.fits"))

        info = [(0, "PRIMARY", 1, "PrimaryHDU", 138, (), "", "")] + [
            (x, "SCI", x, "ImageHDU", 61, (40, 40), "int16", "") for x in range(1, 5)
        ]

        try:
            assert r.info(output=False) == info
        finally:
            r.close()

    def test_open_3(self):
        # Test that HDUs cannot be accessed after the file was closed
        r = fits.open(self.data("test0.fits"))
        r.close()
        with pytest.raises(IndexError) as exc_info:
            r[1]

        # Check that the exception message is the enhanced version, not the
        # default message from list.__getitem__
        assert str(exc_info.value) == (
            "HDU not found, possibly because the index "
            "is out of range, or because the file was "
            "closed before all HDUs were read"
        )

        # Test that HDUs can be accessed with lazy_load_hdus=False
        r = fits.open(self.data("test0.fits"), lazy_load_hdus=False)
        r.close()
        assert isinstance(r[1], fits.ImageHDU)
        assert len(r) == 5

        with pytest.raises(IndexError) as exc_info:
            r[6]
        assert str(exc_info.value) == "list index out of range"

        # And the same with the global config item
        assert fits.conf.lazy_load_hdus  # True by default
        fits.conf.lazy_load_hdus = False
        try:
            r = fits.open(self.data("test0.fits"))
            r.close()
            assert isinstance(r[1], fits.ImageHDU)
            assert len(r) == 5
        finally:
            fits.conf.lazy_load_hdus = True

    def test_fortran_array(self):
        # Test that files are being correctly written+read for "C" and "F" order arrays
        a = np.arange(21).reshape(3, 7)
        b = np.asfortranarray(a)

        afits = self.temp("a_str.fits")
        bfits = self.temp("b_str.fits")
        # writing to str specified files
        fits.PrimaryHDU(data=a).writeto(afits)
        fits.PrimaryHDU(data=b).writeto(bfits)
        np.testing.assert_array_equal(fits.getdata(afits), a)
        np.testing.assert_array_equal(fits.getdata(bfits), a)

        # writing to fileobjs
        aafits = self.temp("a_fileobj.fits")
        bbfits = self.temp("b_fileobj.fits")
        with open(aafits, mode="wb") as fd:
            fits.PrimaryHDU(data=a).writeto(fd)
        with open(bbfits, mode="wb") as fd:
            fits.PrimaryHDU(data=b).writeto(fd)
        np.testing.assert_array_equal(fits.getdata(aafits), a)
        np.testing.assert_array_equal(fits.getdata(bbfits), a)

    def test_fortran_array_non_contiguous(self):
        # Test that files are being correctly written+read for 'C' and 'F' order arrays
        a = np.arange(105).reshape(3, 5, 7)
        b = np.asfortranarray(a)

        # writing to str specified files
        afits = self.temp("a_str_slice.fits")
        bfits = self.temp("b_str_slice.fits")
        fits.PrimaryHDU(data=a[::2, ::2]).writeto(afits)
        fits.PrimaryHDU(data=b[::2, ::2]).writeto(bfits)
        np.testing.assert_array_equal(fits.getdata(afits), a[::2, ::2])
        np.testing.assert_array_equal(fits.getdata(bfits), a[::2, ::2])

        # writing to fileobjs
        aafits = self.temp("a_fileobj_slice.fits")
        bbfits = self.temp("b_fileobj_slice.fits")
        with open(aafits, mode="wb") as fd:
            fits.PrimaryHDU(data=a[::2, ::2]).writeto(fd)
        with open(bbfits, mode="wb") as fd:
            fits.PrimaryHDU(data=b[::2, ::2]).writeto(fd)
        np.testing.assert_array_equal(fits.getdata(aafits), a[::2, ::2])
        np.testing.assert_array_equal(fits.getdata(bbfits), a[::2, ::2])

    def test_primary_with_extname(self):
        """Regression test for https://aeon.stsci.edu/ssb/trac/pyfits/ticket/151

        Tests that the EXTNAME keyword works with Primary HDUs as well, and
        interacts properly with the .name attribute.  For convenience
        hdulist['PRIMARY'] will still refer to the first HDU even if it has an
        EXTNAME not equal to 'PRIMARY'.
        """

        prihdr = fits.Header([("EXTNAME", "XPRIMARY"), ("EXTVER", 1)])
        hdul = fits.HDUList([fits.PrimaryHDU(header=prihdr)])
        assert "EXTNAME" in hdul[0].header
        assert hdul[0].name == "XPRIMARY"
        assert hdul[0].name == hdul[0].header["EXTNAME"]

        info = [(0, "XPRIMARY", 1, "PrimaryHDU", 5, (), "", "")]
        assert hdul.info(output=False) == info

        assert hdul["PRIMARY"] is hdul["XPRIMARY"]
        assert hdul["PRIMARY"] is hdul[("XPRIMARY", 1)]

        hdul[0].name = "XPRIMARY2"
        assert hdul[0].header["EXTNAME"] == "XPRIMARY2"

        hdul.writeto(self.temp("test.fits"))
        with fits.open(self.temp("test.fits")) as hdul:
            assert hdul[0].name == "XPRIMARY2"

    @pytest.mark.filterwarnings(
        "ignore:Memory map object was closed but appears to still be referenced:UserWarning"
    )
    def test_io_manipulation(self):
        # Get a keyword value.  An extension can be referred by name or by
        # number.  Both extension and keyword names are case insensitive.
        with fits.open(self.data("test0.fits")) as r:
            assert r["primary"].header["naxis"] == 0
            assert r[0].header["naxis"] == 0

            # If there are more than one extension with the same EXTNAME value,
            # the EXTVER can be used (as the second argument) to distinguish
            # the extension.
            assert r["sci", 1].header["detector"] == 1

            # append (using "update()") a new card
            r[0].header["xxx"] = 1.234e56

            assert (
                "\n".join(str(x) for x in r[0].header.cards[-3:])
                == "EXPFLAG = 'NORMAL            ' / Exposure interruption indicator                \n"
                "FILENAME= 'vtest3.fits'        / File name                                      \n"
                "XXX     =            1.234E+56                                                  "
            )

            # rename a keyword
            r[0].header.rename_keyword("filename", "fname")
            pytest.raises(ValueError, r[0].header.rename_keyword, "fname", "history")

            pytest.raises(ValueError, r[0].header.rename_keyword, "fname", "simple")
            r[0].header.rename_keyword("fname", "filename")

            # get a subsection of data
            assert np.array_equal(
                r[2].data[:3, :3],
                np.array(
                    [[349, 349, 348], [349, 349, 347], [347, 350, 349]], dtype=np.int16
                ),
            )

            # We can create a new FITS file by opening a new file with "append"
            # mode.
            with fits.open(self.temp("test_new.fits"), mode="append") as n:
                # Append the primary header and the 2nd extension to the new
                # file.
                n.append(r[0])
                n.append(r[2])

                # The flush method will write the current HDUList object back
                # to the newly created file on disk.  The HDUList is still open
                # and can be further operated.
                n.flush()
                assert n[1].data[1, 1] == 349

                # modify a data point
                n[1].data[1, 1] = 99

                # When the file is closed, the most recent additions of
                # extension(s) since last flush() will be appended, but any HDU
                # already existed at the last flush will not be modified
            del n

            # If an existing file is opened with "append" mode, like the
            # readonly mode, the HDU's will be read into the HDUList which can
            # be modified in memory but can not be written back to the original
            # file.  A file opened with append mode can only add new HDU's.
            os.rename(self.temp("test_new.fits"), self.temp("test_append.fits"))

            with fits.open(self.temp("test_append.fits"), mode="append") as a:
                # The above change did not take effect since this was made
                # after the flush().
                assert a[1].data[1, 1] == 349
                a.append(r[1])
            del a

            # When changes are made to an HDUList which was opened with
            # "update" mode, they will be written back to the original file
            # when a flush/close is called.
            os.rename(self.temp("test_append.fits"), self.temp("test_update.fits"))

            with fits.open(self.temp("test_update.fits"), mode="update") as u:
                # When the changes do not alter the size structures of the
                # original (or since last flush) HDUList, the changes are
                # written back "in place".
                assert u[0].header["rootname"] == "U2EQ0201T"
                u[0].header["rootname"] = "abc"
                assert u[1].data[1, 1] == 349
                u[1].data[1, 1] = 99
                u.flush()

                # If the changes affect the size structure, e.g. adding or
                # deleting HDU(s), header was expanded or reduced beyond
                # existing number of blocks (2880 bytes in each block), or
                # change the data size, the HDUList is written to a temporary
                # file, the original file is deleted, and the temporary file is
                # renamed to the original file name and reopened in the update
                # mode.  To a user, these two kinds of updating writeback seem
                # to be the same, unless the optional argument in flush or
                # close is set to 1.
                del u[2]
                u.flush()

                # The write method in HDUList class writes the current HDUList,
                # with all changes made up to now, to a new file.  This method
                # works the same disregard the mode the HDUList was opened
                # with.
                u.append(r[3])
                u.writeto(self.temp("test_new.fits"))
            del u

        # Another useful new HDUList method is readall.  It will "touch" the
        # data parts in all HDUs, so even if the HDUList is closed, we can
        # still operate on the data.
        with fits.open(self.data("test0.fits")) as r:
            r.readall()
            assert r[1].data[1, 1] == 315

        # create an HDU with data only
        data = np.ones((3, 5), dtype=np.float32)
        hdu = fits.ImageHDU(data=data, name="SCI")
        assert np.array_equal(
            hdu.data,
            np.array(
                [
                    [1.0, 1.0, 1.0, 1.0, 1.0],
                    [1.0, 1.0, 1.0, 1.0, 1.0],
                    [1.0, 1.0, 1.0, 1.0, 1.0],
                ],
                dtype=np.float32,
            ),
        )

        # create an HDU with header and data
        # notice that the header has the right NAXIS's since it is constructed
        # with ImageHDU
        hdu2 = fits.ImageHDU(header=r[1].header, data=np.array([1, 2], dtype="int32"))

        assert (
            "\n".join(str(x) for x in hdu2.header.cards[1:5])
            == "BITPIX  =                   32 / array data type                                \n"
            "NAXIS   =                    1 / number of array dimensions                     \n"
            "NAXIS1  =                    2                                                  \n"
            "PCOUNT  =                    0 / number of parameters                           "
        )

    def test_memory_mapping(self):
        # memory mapping
        f1 = fits.open(self.data("test0.fits"), memmap=1)
        f1.close()

    def test_verification_on_output(self):
        # verification on output
        # make a defect HDUList first
        x = fits.ImageHDU()
        hdu = fits.HDUList(x)  # HDUList can take a list or one single HDU

        with pytest.warns(fits.verify.VerifyWarning) as w:
            hdu.verify()
        assert len(w) == 3
        assert "HDUList's 0th element is not a primary HDU" in str(w[1].message)

        with pytest.warns(fits.verify.VerifyWarning) as w:
            hdu.writeto(self.temp("test_new2.fits"), "fix")
        assert len(w) == 3
        assert "Fixed by inserting one as 0th HDU" in str(w[1].message)

    def test_section(self):
        # section testing
        fs = fits.open(self.data("arange.fits"))
        assert fs[0].section.dtype == "int32"
        assert np.array_equal(fs[0].section[3, 2, 5], 357)
        assert np.array_equal(
            fs[0].section[3, 2, :],
            np.array([352, 353, 354, 355, 356, 357, 358, 359, 360, 361, 362]),
        )
        assert np.array_equal(
            fs[0].section[3, 2, 4:], np.array([356, 357, 358, 359, 360, 361, 362])
        )
        assert np.array_equal(
            fs[0].section[3, 2, :8], np.array([352, 353, 354, 355, 356, 357, 358, 359])
        )
        assert np.array_equal(
            fs[0].section[3, 2, -8:8], np.array([355, 356, 357, 358, 359])
        )
        assert np.array_equal(
            fs[0].section[3, 2:5, :],
            np.array(
                [
                    [352, 353, 354, 355, 356, 357, 358, 359, 360, 361, 362],
                    [363, 364, 365, 366, 367, 368, 369, 370, 371, 372, 373],
                    [374, 375, 376, 377, 378, 379, 380, 381, 382, 383, 384],
                ]
            ),
        )

        assert np.array_equal(
            fs[0].section[3, :, :][:3, :3],
            np.array([[330, 331, 332], [341, 342, 343], [352, 353, 354]]),
        )

        dat = fs[0].data
        assert np.array_equal(fs[0].section[3, 2:5, :8], dat[3, 2:5, :8])
        assert np.array_equal(fs[0].section[3, 2:5, 3], dat[3, 2:5, 3])

        assert np.array_equal(
            fs[0].section[3:6, :, :][:3, :3, :3],
            np.array(
                [
                    [[330, 331, 332], [341, 342, 343], [352, 353, 354]],
                    [[440, 441, 442], [451, 452, 453], [462, 463, 464]],
                    [[550, 551, 552], [561, 562, 563], [572, 573, 574]],
                ]
            ),
        )

        assert np.array_equal(
            fs[0].section[:, :, :][:3, :2, :2],
            np.array(
                [[[0, 1], [11, 12]], [[110, 111], [121, 122]], [[220, 221], [231, 232]]]
            ),
        )

        assert np.array_equal(fs[0].section[:, 2, :], dat[:, 2, :])
        assert np.array_equal(fs[0].section[:, 2:5, :], dat[:, 2:5, :])
        assert np.array_equal(fs[0].section[3:6, 3, :], dat[3:6, 3, :])
        assert np.array_equal(fs[0].section[3:6, 3:7, :], dat[3:6, 3:7, :])

        assert np.array_equal(fs[0].section[:, ::2], dat[:, ::2])
        assert np.array_equal(fs[0].section[:, [1, 2, 4], 3], dat[:, [1, 2, 4], 3])
        bool_index = np.array(
            [True, False, True, True, False, False, True, True, False, True]
        )
        assert np.array_equal(fs[0].section[:, bool_index, :], dat[:, bool_index, :])

        assert np.array_equal(fs[0].section[3:6, 3, :, ...], dat[3:6, 3, :, ...])
        assert np.array_equal(fs[0].section[..., ::2], dat[..., ::2])
        assert np.array_equal(fs[0].section[..., [1, 2, 4], 3], dat[..., [1, 2, 4], 3])

        # Can we use negative indices?
        assert np.array_equal(fs[0].section[-1], dat[-1])
        assert np.array_equal(fs[0].section[-9:-7], dat[-9:-7])
        assert np.array_equal(fs[0].section[-4, -6:-3, -1], dat[-4, -6:-3, -1])
        fs.close()

    def test_section_data_single(self):
        a = np.array([1])
        hdu = fits.PrimaryHDU(a)
        hdu.writeto(self.temp("test_new.fits"))

        hdul = fits.open(self.temp("test_new.fits"))
        sec = hdul[0].section
        dat = hdul[0].data
        assert np.array_equal(sec[0], dat[0])
        assert np.array_equal(sec[...], dat[...])
        assert np.array_equal(sec[..., 0], dat[..., 0])
        assert np.array_equal(sec[0, ...], dat[0, ...])
        hdul.close()

    def test_section_data_square(self):
        a = np.arange(4).reshape(2, 2)
        hdu = fits.PrimaryHDU(a)
        hdu.writeto(self.temp("test_new.fits"))

        hdul = fits.open(self.temp("test_new.fits"))
        d = hdul[0]
        dat = hdul[0].data
        assert (d.section[:, :] == dat[:, :]).all()
        assert (d.section[0, :] == dat[0, :]).all()
        assert (d.section[1, :] == dat[1, :]).all()
        assert (d.section[:, 0] == dat[:, 0]).all()
        assert (d.section[:, 1] == dat[:, 1]).all()
        assert (d.section[0, 0] == dat[0, 0]).all()
        assert (d.section[0, 1] == dat[0, 1]).all()
        assert (d.section[1, 0] == dat[1, 0]).all()
        assert (d.section[1, 1] == dat[1, 1]).all()
        assert (d.section[0:1, 0:1] == dat[0:1, 0:1]).all()
        assert (d.section[0:2, 0:1] == dat[0:2, 0:1]).all()
        assert (d.section[0:1, 0:2] == dat[0:1, 0:2]).all()
        assert (d.section[0:2, 0:2] == dat[0:2, 0:2]).all()
        hdul.close()

    def test_section_data_cube(self):
        a = np.arange(18).reshape(2, 3, 3)
        hdu = fits.PrimaryHDU(a)
        hdu.writeto(self.temp("test_new.fits"))

        hdul = fits.open(self.temp("test_new.fits"))
        d = hdul[0]
        dat = hdul[0].data

        assert (d.section[:] == dat[:]).all()
        assert (d.section[:, :] == dat[:, :]).all()

        # Test that various combinations of indexing on the section are equal to
        # indexing the data.
        # Testing all combinations of scalar-index and [:] for each dimension.
        for idx1 in [slice(None), 0, 1]:
            for idx2 in [slice(None), 0, 1, 2]:
                for idx3 in [slice(None), 0, 1, 2]:
                    nd_idx = (idx1, idx2, idx3)
                    assert (d.section[nd_idx] == dat[nd_idx]).all()

        # Test all ways to slice the last dimension but keeping the first two.
        for idx3 in [
            slice(0, 1),
            slice(0, 2),
            slice(0, 3),
            slice(1, 2),
            slice(1, 3),
            slice(2, 3),
        ]:
            nd_idx = (slice(None), slice(None), idx3)
            assert (d.section[nd_idx] == dat[nd_idx]).all()

        # Test various combinations (not exhaustive) to slice all dimensions.
        for idx1 in [slice(0, 1), slice(1, 2)]:
            for idx2 in [
                slice(0, 1),
                slice(0, 2),
                slice(0, 3),
                slice(1, 2),
                slice(1, 3),
            ]:
                for idx3 in [
                    slice(0, 1),
                    slice(0, 2),
                    slice(0, 3),
                    slice(1, 2),
                    slice(1, 3),
                    slice(2, 3),
                ]:
                    nd_idx = (idx1, idx2, idx3)
                    assert (d.section[nd_idx] == dat[nd_idx]).all()

        hdul.close()

    def test_section_data_four(self):
        a = np.arange(256).reshape(4, 4, 4, 4)
        hdu = fits.PrimaryHDU(a)
        hdu.writeto(self.temp("test_new.fits"))

        hdul = fits.open(self.temp("test_new.fits"))
        d = hdul[0]
        dat = hdul[0].data
        assert (d.section[:, :, :, :] == dat[:, :, :, :]).all()
        assert (d.section[:, :, :] == dat[:, :, :]).all()
        assert (d.section[:, :] == dat[:, :]).all()
        assert (d.section[:] == dat[:]).all()
        assert (d.section[0, :, :, :] == dat[0, :, :, :]).all()
        assert (d.section[0, :, 0, :] == dat[0, :, 0, :]).all()
        assert (d.section[:, :, 0, :] == dat[:, :, 0, :]).all()
        assert (d.section[:, 1, 0, :] == dat[:, 1, 0, :]).all()
        assert (d.section[:, :, :, 1] == dat[:, :, :, 1]).all()
        hdul.close()

    @pytest.mark.parametrize(
        "file, expected_dtype",
        [("scale.fits", "float32"), ("fixed-1890.fits", "uint16")],
    )
    def test_section_data_scaled(self, file, expected_dtype):
        """
        Regression test for https://aeon.stsci.edu/ssb/trac/pyfits/ticket/143

        This is like test_section_data_square but uses a file containing scaled
        image data, to test that sections can work correctly with scaled data.
        """

        hdul = fits.open(self.data(file))
        d = hdul[0]
        dat = hdul[0].data
        assert d.section.dtype == expected_dtype
        assert (d.section[:, :] == dat[:, :]).all()
        assert (d.section[0, :] == dat[0, :]).all()
        assert (d.section[1, :] == dat[1, :]).all()
        assert (d.section[:, 0] == dat[:, 0]).all()
        assert (d.section[:, 1] == dat[:, 1]).all()
        assert (d.section[0, 0] == dat[0, 0]).all()
        assert (d.section[0, 1] == dat[0, 1]).all()
        assert (d.section[1, 0] == dat[1, 0]).all()
        assert (d.section[1, 1] == dat[1, 1]).all()
        assert (d.section[0:1, 0:1] == dat[0:1, 0:1]).all()
        assert (d.section[0:2, 0:1] == dat[0:2, 0:1]).all()
        assert (d.section[0:1, 0:2] == dat[0:1, 0:2]).all()
        assert (d.section[0:2, 0:2] == dat[0:2, 0:2]).all()
        hdul.close()

        # Test without having accessed the full data first
        hdul = fits.open(self.data(file))
        d = hdul[0]
        assert d.section.dtype == expected_dtype
        assert (d.section[:, :] == dat[:, :]).all()
        assert (d.section[0, :] == dat[0, :]).all()
        assert (d.section[1, :] == dat[1, :]).all()
        assert (d.section[:, 0] == dat[:, 0]).all()
        assert (d.section[:, 1] == dat[:, 1]).all()
        assert (d.section[0, 0] == dat[0, 0]).all()
        assert (d.section[0, 1] == dat[0, 1]).all()
        assert (d.section[1, 0] == dat[1, 0]).all()
        assert (d.section[1, 1] == dat[1, 1]).all()
        assert (d.section[0:1, 0:1] == dat[0:1, 0:1]).all()
        assert (d.section[0:2, 0:1] == dat[0:2, 0:1]).all()
        assert (d.section[0:1, 0:2] == dat[0:1, 0:2]).all()
        assert (d.section[0:2, 0:2] == dat[0:2, 0:2]).all()
        assert not d._data_loaded
        hdul.close()

    def test_do_not_scale_image_data(self):
        with fits.open(self.data("scale.fits"), do_not_scale_image_data=True) as hdul:
            assert hdul[0].data.dtype == np.dtype(">i2")

        with fits.open(self.data("scale.fits")) as hdul:
            assert hdul[0].data.dtype == np.dtype("float32")

    def test_append_uint_data(self):
        """Regression test for https://aeon.stsci.edu/ssb/trac/pyfits/ticket/56
        (BZERO and BSCALE added in the wrong location when appending scaled
        data)
        """

        fits.writeto(self.temp("test_new.fits"), data=np.array([], dtype="uint8"))
        d = np.zeros([100, 100]).astype("uint16")
        fits.append(self.temp("test_new.fits"), data=d)

        with fits.open(self.temp("test_new.fits"), uint=True) as f:
            assert f[1].data.dtype == "uint16"

    def test_scale_with_explicit_bzero_bscale(self):
        """
        Regression test for https://github.com/astropy/astropy/issues/6399
        """
        hdu2 = fits.ImageHDU(np.random.rand(100, 100))
        # The line below raised an exception in astropy 2.0, so if it does not
        # raise an error here, that is progress.
        hdu2.scale(type="uint8", bscale=1, bzero=0)

    def test_uint_header_consistency(self):
        """
        Regression test for https://github.com/astropy/astropy/issues/2305

        This ensures that an HDU containing unsigned integer data always has
        the appropriate BZERO value in its header.
        """

        for int_size in (16, 32, 64):
            # Just make an array of some unsigned ints that wouldn't fit in a
            # signed int array of the same bit width
            max_uint = (2**int_size) - 1
            if int_size == 64:
                max_uint = np.uint64(int_size)

            dtype = f"uint{int_size}"
            arr = np.empty(100, dtype=dtype)
            arr.fill(max_uint)
            arr -= np.arange(100, dtype=dtype)

            uint_hdu = fits.PrimaryHDU(data=arr)
            assert np.all(uint_hdu.data == arr)
            assert uint_hdu.data.dtype.name == f"uint{int_size}"
            assert "BZERO" in uint_hdu.header
            assert uint_hdu.header["BZERO"] == (2 ** (int_size - 1))

            filename = f"uint{int_size}.fits"
            uint_hdu.writeto(self.temp(filename))

            with fits.open(self.temp(filename), uint=True) as hdul:
                new_uint_hdu = hdul[0]
                assert np.all(new_uint_hdu.data == arr)
                assert new_uint_hdu.data.dtype.name == f"uint{int_size}"
                assert "BZERO" in new_uint_hdu.header
                assert new_uint_hdu.header["BZERO"] == (2 ** (int_size - 1))

    @pytest.mark.parametrize(("from_file"), (False, True))
    @pytest.mark.parametrize(("do_not_scale"), (False,))
    def test_uint_header_keywords_removed_after_bitpix_change(
        self, from_file, do_not_scale
    ):
        """
        Regression test for https://github.com/astropy/astropy/issues/4974

        BZERO/BSCALE should be removed if data is converted to a floating
        point type.

        Currently excluding the case where do_not_scale_image_data=True
        because it is not clear what the expectation should be.
        """

        arr = np.zeros(100, dtype="uint16")

        if from_file:
            # To generate the proper input file we always want to scale the
            # data before writing it...otherwise when we open it will be
            # regular (signed) int data.
            tmp_uint = fits.PrimaryHDU(arr)
            filename = "unsigned_int.fits"
            tmp_uint.writeto(self.temp(filename))
            with fits.open(
                self.temp(filename), do_not_scale_image_data=do_not_scale
            ) as f:
                uint_hdu = f[0]
                # Force a read before we close.
                _ = uint_hdu.data
        else:
            uint_hdu = fits.PrimaryHDU(arr, do_not_scale_image_data=do_not_scale)

        # Make sure appropriate keywords are in the header. See
        # https://github.com/astropy/astropy/pull/3916#issuecomment-122414532
        # for discussion.
        assert "BSCALE" in uint_hdu.header
        assert "BZERO" in uint_hdu.header
        assert uint_hdu.header["BSCALE"] == 1
        assert uint_hdu.header["BZERO"] == 32768

        # Convert data to floating point...
        uint_hdu.data = uint_hdu.data * 1.0

        # ...bitpix should be negative.
        assert uint_hdu.header["BITPIX"] < 0

        # BSCALE and BZERO should NOT be in header any more.
        assert "BSCALE" not in uint_hdu.header
        assert "BZERO" not in uint_hdu.header

        # This is the main test...the data values should round trip
        # as zero.
        filename = "test_uint_to_float.fits"
        uint_hdu.writeto(self.temp(filename))
        with fits.open(self.temp(filename)) as hdul:
            assert (hdul[0].data == 0).all()

    def test_blanks(self):
        """Test image data with blank spots in it (which should show up as
        NaNs in the data array.
        """

        arr = np.zeros((10, 10), dtype=np.int32)
        # One row will be blanks
        arr[1] = 999
        hdu = fits.ImageHDU(data=arr)
        hdu.header["BLANK"] = 999
        hdu.writeto(self.temp("test_new.fits"))

        with fits.open(self.temp("test_new.fits")) as hdul:
            assert np.isnan(hdul[1].data[1]).all()

    def test_invalid_blanks(self):
        """
        Test that invalid use of the BLANK keyword leads to an appropriate
        warning, and that the BLANK keyword is ignored when returning the
        HDU data.

        Regression test for https://github.com/astropy/astropy/issues/3865
        """

        arr = np.arange(5, dtype=np.float64)
        hdu = fits.PrimaryHDU(data=arr)
        hdu.header["BLANK"] = 2

        with pytest.warns(
            AstropyUserWarning, match="Invalid 'BLANK' keyword in header"
        ) as w:
            hdu.writeto(self.temp("test_new.fits"))
        # Allow the HDU to be written, but there should be a warning
        # when writing a header with BLANK when then data is not
        # int
        assert len(w) == 1

        # Should also get a warning when opening the file, and the BLANK
        # value should not be applied
        with pytest.warns(
            AstropyUserWarning, match="Invalid 'BLANK' keyword in header"
        ) as w:
            with fits.open(self.temp("test_new.fits")) as h:
                assert np.all(arr == h[0].data)
        assert len(w) == 1

    @pytest.mark.filterwarnings("ignore:Invalid 'BLANK' keyword in header")
    def test_scale_back_with_blanks(self):
        """
        Test that when auto-rescaling integer data with "blank" values (where
        the blanks are replaced by NaN in the float data), that the "BLANK"
        keyword is removed from the header.

        Further, test that when using the ``scale_back=True`` option the blank
        values are restored properly.

        Regression test for https://github.com/astropy/astropy/issues/3865
        """

        # Make the sample file
        arr = np.arange(5, dtype=np.int32)
        hdu = fits.PrimaryHDU(data=arr)
        hdu.scale("int16", bscale=1.23)

        # Creating data that uses BLANK is currently kludgy--a separate issue
        # TODO: Rewrite this test when scaling with blank support is better
        # supported

        # Let's just add a value to the data that should be converted to NaN
        # when it is read back in:
        filename = self.temp("test.fits")
        hdu.data[0] = 9999
        hdu.header["BLANK"] = 9999
        hdu.writeto(filename)

        with fits.open(filename) as hdul:
            data = hdul[0].data
            assert np.isnan(data[0])
            with pytest.warns(
                fits.verify.VerifyWarning, match=r"Invalid 'BLANK' keyword in header"
            ):
                hdul.writeto(self.temp("test2.fits"))

        # Now reopen the newly written file.  It should not have a 'BLANK'
        # keyword
        with fits.open(self.temp("test2.fits")) as hdul2:
            assert "BLANK" not in hdul2[0].header
            data = hdul2[0].data
            assert np.isnan(data[0])

        # Finally, test that scale_back keeps the BLANKs correctly
        with fits.open(filename, scale_back=True, mode="update") as hdul3:
            data = hdul3[0].data
            # This emits warning that pytest cannot catch properly, so we
            # catch it with pytest.mark.filterwarnings above.
            assert np.isnan(data[0])

        with fits.open(filename, do_not_scale_image_data=True) as hdul4:
            assert hdul4[0].header["BLANK"] == 9999
            assert hdul4[0].header["BSCALE"] == 1.23
            assert hdul4[0].data[0] == 9999

    def test_bzero_with_floats(self):
        """Test use of the BZERO keyword in an image HDU containing float
        data.
        """

        arr = np.zeros((10, 10)) - 1
        hdu = fits.ImageHDU(data=arr)
        hdu.header["BZERO"] = 1.0
        hdu.writeto(self.temp("test_new.fits"))

        with fits.open(self.temp("test_new.fits")) as hdul:
            arr += 1
            assert (hdul[1].data == arr).all()

    def test_rewriting_large_scaled_image(self):
        """Regression test for https://aeon.stsci.edu/ssb/trac/pyfits/ticket/84 and
        https://aeon.stsci.edu/ssb/trac/pyfits/ticket/101
        """

        hdul = fits.open(self.data("fixed-1890.fits"))
        orig_data = hdul[0].data
        hdul.writeto(self.temp("test_new.fits"), overwrite=True)
        hdul.close()
        hdul = fits.open(self.temp("test_new.fits"))
        assert (hdul[0].data == orig_data).all()
        hdul.close()

        # Just as before, but this time don't touch hdul[0].data before writing
        # back out--this is the case that failed in
        # https://aeon.stsci.edu/ssb/trac/pyfits/ticket/84
        hdul = fits.open(self.data("fixed-1890.fits"))
        hdul.writeto(self.temp("test_new.fits"), overwrite=True)
        hdul.close()
        hdul = fits.open(self.temp("test_new.fits"))
        assert (hdul[0].data == orig_data).all()
        hdul.close()

        # Test opening/closing/reopening a scaled file in update mode
        hdul = fits.open(self.data("fixed-1890.fits"), do_not_scale_image_data=True)
        hdul.writeto(
            self.temp("test_new.fits"), overwrite=True, output_verify="silentfix"
        )
        hdul.close()
        hdul = fits.open(self.temp("test_new.fits"))
        orig_data = hdul[0].data
        hdul.close()
        hdul = fits.open(self.temp("test_new.fits"), mode="update")
        hdul.close()
        hdul = fits.open(self.temp("test_new.fits"))
        assert (hdul[0].data == orig_data).all()
        hdul.close()

    def test_image_update_header(self):
        """
        Regression test for https://aeon.stsci.edu/ssb/trac/pyfits/ticket/105

        Replacing the original header to an image HDU and saving should update
        the NAXISn keywords appropriately and save the image data correctly.
        """

        # Copy the original file before saving to it
        self.copy_file("test0.fits")
        with fits.open(self.temp("test0.fits"), mode="update") as hdul:
            orig_data = hdul[1].data.copy()
            hdr_copy = hdul[1].header.copy()
            del hdr_copy["NAXIS*"]
            hdul[1].header = hdr_copy

        with fits.open(self.temp("test0.fits")) as hdul:
            assert (orig_data == hdul[1].data).all()

    def test_open_scaled_in_update_mode(self):
        """
        Regression test for https://aeon.stsci.edu/ssb/trac/pyfits/ticket/119
        (Don't update scaled image data if the data is not read)

        This ensures that merely opening and closing a file containing scaled
        image data does not cause any change to the data (or the header).
        Changes should only occur if the data is accessed.
        """

        # Copy the original file before making any possible changes to it
        self.copy_file("scale.fits")
        mtime = os.stat(self.temp("scale.fits")).st_mtime

        time.sleep(1)

        fits.open(self.temp("scale.fits"), mode="update").close()

        # Ensure that no changes were made to the file merely by immediately
        # opening and closing it.
        assert mtime == os.stat(self.temp("scale.fits")).st_mtime

        # Insert a slight delay to ensure the mtime does change when the file
        # is changed
        time.sleep(1)

        hdul = fits.open(self.temp("scale.fits"), "update")
        orig_data = hdul[0].data
        hdul.close()

        # Now the file should be updated with the rescaled data
        assert mtime != os.stat(self.temp("scale.fits")).st_mtime
        hdul = fits.open(self.temp("scale.fits"), mode="update")
        assert hdul[0].data.dtype == np.dtype(">f4")
        assert hdul[0].header["BITPIX"] == -32
        assert "BZERO" not in hdul[0].header
        assert "BSCALE" not in hdul[0].header
        assert (orig_data == hdul[0].data).all()

        # Try reshaping the data, then closing and reopening the file; let's
        # see if all the changes are preserved properly
        hdul[0].data.shape = (42, 10)
        hdul.close()

        hdul = fits.open(self.temp("scale.fits"))
        assert hdul[0].shape == (42, 10)
        assert hdul[0].data.dtype == np.dtype(">f4")
        assert hdul[0].header["BITPIX"] == -32
        assert "BZERO" not in hdul[0].header
        assert "BSCALE" not in hdul[0].header
        hdul.close()

    def test_scale_back(self):
        """A simple test for https://aeon.stsci.edu/ssb/trac/pyfits/ticket/120

        The scale_back feature for image HDUs.
        """

        self.copy_file("scale.fits")
        with fits.open(self.temp("scale.fits"), mode="update", scale_back=True) as hdul:
            orig_bitpix = hdul[0].header["BITPIX"]
            orig_bzero = hdul[0].header["BZERO"]
            orig_bscale = hdul[0].header["BSCALE"]
            orig_data = hdul[0].data.copy()
            hdul[0].data[0] = 0

        with fits.open(self.temp("scale.fits"), do_not_scale_image_data=True) as hdul:
            assert hdul[0].header["BITPIX"] == orig_bitpix
            assert hdul[0].header["BZERO"] == orig_bzero
            assert hdul[0].header["BSCALE"] == orig_bscale

            zero_point = math.floor(-orig_bzero / orig_bscale)
            assert (hdul[0].data[0] == zero_point).all()

        with fits.open(self.temp("scale.fits")) as hdul:
            assert (hdul[0].data[1:] == orig_data[1:]).all()

    def test_image_none(self):
        """
        Regression test for https://github.com/spacetelescope/PyFITS/issues/27
        """

        with fits.open(self.data("test0.fits")) as h:
            h[1].data
            h[1].data = None
            h[1].writeto(self.temp("test.fits"))

        with fits.open(self.temp("test.fits")) as h:
            assert h[1].data is None
            assert h[1].header["NAXIS"] == 0
            assert "NAXIS1" not in h[1].header
            assert "NAXIS2" not in h[1].header

    def test_invalid_blank(self):
        """
        Regression test for https://github.com/astropy/astropy/issues/2711

        If the BLANK keyword contains an invalid value it should be ignored for
        any calculations (though a warning should be issued).
        """

        data = np.arange(100, dtype=np.float64)
        hdu = fits.PrimaryHDU(data)
        hdu.header["BLANK"] = "nan"

        with pytest.warns(fits.verify.VerifyWarning) as w:
            hdu.writeto(self.temp("test.fits"))
        assert "Invalid value for 'BLANK' keyword in header: 'nan'" in str(w[0].message)

        with pytest.warns(AstropyUserWarning) as w:
            with fits.open(self.temp("test.fits")) as hdul:
                assert np.all(hdul[0].data == data)

        assert len(w) == 2
        msg = "Invalid value for 'BLANK' keyword in header"
        assert msg in str(w[0].message)
        msg = "Invalid 'BLANK' keyword"
        assert msg in str(w[1].message)

    def test_scaled_image_fromfile(self):
        """
        Regression test for https://github.com/astropy/astropy/issues/2710
        """

        # Make some sample data
        a = np.arange(100, dtype=np.float32)

        hdu = fits.PrimaryHDU(data=a.copy())
        hdu.scale(bscale=1.1)
        hdu.writeto(self.temp("test.fits"))

        with open(self.temp("test.fits"), "rb") as f:
            file_data = f.read()

        hdul = fits.HDUList.fromstring(file_data)
        assert np.allclose(hdul[0].data, a)

    def test_set_data(self):
        """
        Test data assignment - issue #5087
        """

        im = fits.ImageHDU()
        ar = np.arange(12)
        im.data = ar

    def test_scale_bzero_with_int_data(self):
        """
        Regression test for https://github.com/astropy/astropy/issues/4600
        """

        a = np.arange(100, 200, dtype=np.int16)

        hdu1 = fits.PrimaryHDU(data=a.copy())
        hdu2 = fits.PrimaryHDU(data=a.copy())
        # Previously the following line would throw a TypeError,
        # now it should be identical to the integer bzero case
        hdu1.scale("int16", bzero=99.0)
        hdu2.scale("int16", bzero=99)
        assert np.allclose(hdu1.data, hdu2.data)

    def test_scale_back_uint_assignment(self):
        """
        Extend fix for #4600 to assignment to data

        Suggested by:
        https://github.com/astropy/astropy/pull/4602#issuecomment-208713748
        """

        a = np.arange(100, 200, dtype=np.uint16)
        fits.PrimaryHDU(a).writeto(self.temp("test.fits"))
        with fits.open(self.temp("test.fits"), mode="update", scale_back=True) as (
            hdu,
        ):
            hdu.data[:] = 0
            assert np.allclose(hdu.data, 0)

    def test_hdu_creation_with_scalar(self):
        msg = r"data object array\(1\) should have at least one dimension"
        with pytest.raises(TypeError, match=msg):
            fits.ImageHDU(data=1)
        with pytest.raises(TypeError, match=msg):
            fits.PrimaryHDU(data=1)
        # Regression test for https://github.com/astropy/astropy/issues/14527
        with pytest.raises(TypeError, match=msg):
            fits.ImageHDU(data=np.array(1))
        with pytest.raises(TypeError, match=msg):
            fits.PrimaryHDU(data=np.array(1))


def test_scale_implicit_casting():
    # Regression test for an issue that occurred because Numpy now does not
    # allow implicit type casting during inplace operations.

    hdu = fits.ImageHDU(np.array([1], dtype=np.int32))
    hdu.scale(bzero=1.3)


def test_scale_floats():
    data = np.arange(10) / 10
    hdu = fits.ImageHDU(data)
    hdu.scale("float32")
    np.testing.assert_array_equal(hdu.data, data.astype("float32"))


def test_bzero_implicit_casting_compressed():
    # Regression test for an issue that occurred because Numpy now does not
    # allow implicit type casting during inplace operations. Astropy is
    # actually not able to produce a file that triggers the failure - the
    # issue occurs when using unsigned integer types in the FITS file, in which
    # case BZERO should be 32768. But if the keyword is stored as 32768.0, then
    # it was possible to trigger the implicit casting error.

    filename = get_pkg_data_filename("data/compressed_float_bzero.fits")

    with fits.open(filename) as hdul:
        hdu = hdul[1]
        hdu.data


def test_bzero_mishandled_info(tmp_path):
    # Regression test for #5507:
    # Calling HDUList.info() on a dataset which applies a zeropoint
    # from BZERO but which astropy.io.fits does not think it needs
    # to resize to a new dtype results in an AttributeError.
    filename = tmp_path / "floatimg_with_bzero.fits"
    hdu = fits.ImageHDU(np.zeros((10, 10)))
    hdu.header["BZERO"] = 10
    hdu.writeto(filename, overwrite=True)
    with fits.open(filename) as hdul:
        hdul.info()


def test_image_write_readonly(tmp_path):
    # Regression test to make sure that we can write out read-only arrays (#5512)

    x = np.array([1, 2, 3])
    x.setflags(write=False)
    ghdu = fits.ImageHDU(data=x)
    ghdu.add_datasum()

    filename = tmp_path / "test.fits"

    ghdu.writeto(filename)

    with fits.open(filename) as hdulist:
        assert_equal(hdulist[1].data, [1, 2, 3])


def test_int8(tmp_path):
    """Test for int8 support, https://github.com/astropy/astropy/issues/11995"""
    img = np.arange(-50, 50, dtype=np.int8).reshape(10, 10)
    hdu = fits.PrimaryHDU(img)
    hdu.writeto(tmp_path / "int8.fits")

    with fits.open(tmp_path / "int8.fits") as hdul:
        assert hdul[0].header["BITPIX"] == 8
        assert hdul[0].header["BZERO"] == -128
        assert hdul[0].header["BSCALE"] == 1.0
        assert_equal(hdul[0].data, img)
        assert hdul[0].data.dtype == img.dtype
