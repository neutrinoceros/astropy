// This extension is adapted from the positional_defaults PyPI package
// https://pypi.org/project/positional-defaults/
// version 2023.4.19

// MIT License

// Copyright (c) 2023 Nicolas Tessore

// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:

// The above copyright notice and this permission notice shall be included in all
// copies or substantial portions of the Software.

// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
// SOFTWARE.

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <structmember.h>


typedef struct {
    PyObject_HEAD
    PyObject* dict;
    PyObject* wrapped;
    PyObject* names;
    PyObject* signature;
} WrapObject;



static void
wrap_dealloc(WrapObject* self)
{
    Py_XDECREF(self->wrapped);
    Py_XDECREF(self->names);
    Py_XDECREF(self->signature);
    Py_TYPE(self)->tp_free((PyObject*)self);
}


static PyObject*
wrap_new(PyTypeObject* type, PyObject* args, PyObject* kwds) {
    WrapObject* self = (WrapObject*)type->tp_alloc(type, 0);

    if (self != NULL) {
        self->names = PyTuple_New(0);
        if (self->names == NULL) {
            Py_DECREF(self);
            return NULL;
        }

        Py_INCREF(Py_None);
        self->wrapped = Py_None;

        Py_INCREF(Py_None);
        self->signature = Py_None;
    }

    return (PyObject*)self;
}


static int
wrap_init(WrapObject* self, PyObject* args, PyObject* kwds)
{
    static char *kwlist[] = {"wrapped", "names", "signature", NULL};
    Py_ssize_t i, n_names;
    PyObject* wrapped, *names, *signature, *tmp;

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "OOO:wrap", kwlist,
                                     &wrapped, &names, &signature))
        return -1;

    if (!PyTuple_Check(names)) {
        PyErr_SetString(PyExc_TypeError, "names must be a tuple");
        return -1;
    }

    n_names = PyTuple_GET_SIZE(names);

    for (i = 0; i < n_names; ++i) {
        PyObject* name = PyTuple_GET_ITEM(names, i);
        if (!PyUnicode_Check(name)) {
            PyErr_Format(PyExc_TypeError, "names[%zd] must be a string", i);
            return -1;
        }
    }

    tmp = self->wrapped;
    Py_INCREF(wrapped);
    self->wrapped = wrapped;
    Py_XDECREF(tmp);

    tmp = self->names;
    Py_INCREF(names);
    self->names = names;
    Py_XDECREF(tmp);

    tmp = self->signature;
    Py_INCREF(signature);
    self->signature = signature;
    Py_XDECREF(tmp);

    return 0;
}


static PyMemberDef wrap_members[] = {
    {"__dict__", T_OBJECT, offsetof(WrapObject, dict), READONLY},
    {"wrapped", T_OBJECT, offsetof(WrapObject, wrapped), READONLY},
    {"names", T_OBJECT, offsetof(WrapObject, names), READONLY},
    {"signature", T_OBJECT, offsetof(WrapObject, signature), READONLY},
    {NULL}
};


static PyObject*
wrap_call(WrapObject* self, PyObject* args, PyObject* kwds) {
    // step 0: return early whenever possible
    if (self->wrapped == NULL)
        Py_RETURN_NONE;

    if (kwds == NULL)
        return PyObject_Call(self->wrapped, args, kwds);

    // step 1: detect any deprecated keyword arguments, return if none.
    Py_ssize_t n_names = PyTuple_GET_SIZE(self->names);
    PyObject *deprecated_kwargs = PyList_New(n_names);
    Py_INCREF(deprecated_kwargs);
    PyObject *name = NULL;
    Py_ssize_t i = 0;
    int has_kw = -2;

    Py_ssize_t n_depr = 0;
    for (i=0 ; i < n_names ; ++i) {
        name = PyTuple_GET_ITEM(self->names, i);
        has_kw = PyDict_Contains(kwds, name);
        if (has_kw) {
            PyList_SET_ITEM(deprecated_kwargs, n_depr, name);
            ++n_depr;
        }
    }

    if (n_depr == 0)
        return PyObject_Call(self->wrapped, args, kwds);

    // step 2: create and emit warning message
    char *names_str = "";
    char *s, *arguments, *respectively, *pronoun;

    Py_ssize_t size = 0;
    PyObject *names_unicode;
    if (n_depr > 1) {
        names_unicode = PyObject_Str(PyList_GetSlice(deprecated_kwargs, 0, n_depr));
        s = "s";
        arguments = " arguments";
        respectively = ", respectively";
        pronoun = "them";
    } else {
        names_unicode = PyObject_Repr(PyList_GET_ITEM(deprecated_kwargs, 0));
        s = arguments = respectively = "";
        pronoun = "it";
    }
    const char* names__ = PyUnicode_AsUTF8AndSize(names_unicode, &size);
    sprintf(names_str, "%s", names__);

    char *msg = "";
    sprintf(
        msg,
        "Passing %s%s as keyword%s "
        "is deprecated and will stop working in a future release. "
        "Pass %s positionally to suppress this warning.",
        names_str, arguments, s, pronoun
    );

    int status = PyErr_WarnEx(PyExc_FutureWarning, msg, 2);
    if (status == -1) {
        // avoid leaking memory if Warning is promoted to Exception
        Py_DECREF(deprecated_kwargs);
    }

    return PyObject_Call(self->wrapped, args, kwds);
}


static PyObject*
wrap_get(PyObject* self, PyObject* obj, PyObject* type) {
    if (obj == Py_None || obj == NULL) {
        Py_INCREF(self);
        return self;
    }
    return PyMethod_New(self, obj);
}


static PyTypeObject WrapType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "_future_positional_only.wrap",
    .tp_doc = PyDoc_STR("wrap (C impl)"),
    .tp_basicsize = sizeof(WrapObject),
    .tp_itemsize = 0,
    .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
    .tp_dictoffset = offsetof(WrapObject, dict),
    .tp_new = wrap_new,
    .tp_init = (initproc)wrap_init,
    .tp_dealloc = (destructor)wrap_dealloc,
    .tp_members = wrap_members,
    .tp_call = (ternaryfunc)wrap_call,
    .tp_descr_get = wrap_get,
};


static struct PyModuleDef module = {
    PyModuleDef_HEAD_INIT,
    .m_name = "_positional_defaults",
    .m_doc = PyDoc_STR("Implementation of the positional_defaults package."),
    .m_size = -1,
};


PyMODINIT_FUNC
PyInit__future_positional_only(void) {
    PyObject* m;

    if (PyType_Ready(&WrapType) < 0)
        return NULL;

    m = PyModule_Create(&module);
    if (m == NULL)
        return NULL;

    Py_INCREF(&WrapType);
    if (PyModule_AddObject(m, "wrap", (PyObject*)&WrapType) < 0) {
        Py_DECREF(&WrapType);
        Py_DECREF(m);
        return NULL;
    }

    return m;
}
