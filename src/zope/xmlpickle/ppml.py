##############################################################################
#
# Copyright (c) 2001 Zope Corporation and Contributors. All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################
"""Provide conversion between Python pickles and XML.

$Id$
"""
# TODO: This doesn't work properly for protocol 2 pickles yet; that
# still needs to be dealt with.  Particular issues that need to be
# addressed involve supporting the changes for new-style objects.

import base64
import marshal
import re
import struct

from pickle import Unpickler
from pickle import \
     PERSID, NONE, INT, BININT, BININT1, BININT2, LONG, FLOAT, \
     BINFLOAT, STRING, BINSTRING, SHORT_BINSTRING, UNICODE, \
     BINUNICODE, TUPLE, EMPTY_TUPLE, EMPTY_LIST, EMPTY_DICT, LIST, \
     DICT, INST, OBJ, GLOBAL, REDUCE, GET, BINGET, LONG_BINGET, PUT, \
     BINPUT, LONG_BINPUT, STOP, MARK, BUILD, SETITEMS, SETITEM, \
     BINPERSID, APPEND, APPENDS

try:
    from pickle import NEWTRUE, NEWFALSE
except ImportError:
    TRUE = INT + "01\n"
    FALSE = INT + "00\n"
    _bool_support = False
else:
    TRUE = NEWTRUE
    FALSE = NEWFALSE
    _bool_support = True

from cStringIO import StringIO

mdumps = marshal.dumps
mloads = marshal.loads

identifier = re.compile("^[_a-zA-Z][_a-zA-Z0-9]{1,40}$").match



def _convert_sub(string):

    # We don't want to get returns "normalized away, so we quote them
    # This means we can't use cdata.
    rpos = string.find('\r')

    lpos = string.find('<')
    apos = string.find('&')

    if rpos >= 0 or lpos >= 0 or apos >= 0:

        # Need to do something about special characters
        if rpos < 0 and string.find(']]>') < 0:
            # can use cdata
            string = "<![CDATA[%s]]>" % string
        else:

            if apos >= 0:
                string = string.replace("&", "&amp;")
            if lpos >= 0:
                string = string.replace("<", "&lt;")
            if rpos >= 0:
                string = string.replace("\r", "&#x0d;")

    return '', string


#  Function unconvert takes a encoding and a string and
#  returns the original string

def unconvert_string(encoding, string):
    if encoding == 'base64':
        return base64.decodestring(string)
    elif encoding:
        raise ValueError('bad encoding', encoding)

    return string

def unconvert_unicode(encoding, string):
    if encoding == 'base64':
        string = base64.decodestring(string.encode('ascii'))
    elif encoding:
        raise ValueError('bad encoding', encoding)

    return string


class Base(object):

    id = ''

    def __str__(self):
        result = []
        self.output(result.append)

        return ''.join(result)

    def output(self, data, indent=0):
        raise TypeError("No output method defined")

    def __eq__(self, other):
        if self is other:
            return 1
        if type(self) != type(other):
            return 1
        return self.__dict__ == other.__dict__

class Global(Base):

    def __init__(self, module, name):
        self.module=module
        self.name=name

    def output(self, write, indent=0):
        if self.id:
            id = ' id="%s"' % self.id
        else:
            id = ''

        name = self.__class__.__name__.lower()
        write(
            '%s<%s%s name="%s" module="%s"/>\n' % (
            ' '*indent, name, id, self.name, self.module)
            )

_reconstructor_global = Global('copy_reg', '_reconstructor')
_object_global = Global('__builtin__', 'object')

class Scalar(Base):

    def __init__(self, v):
        self._v=v

    def value(self):
        return self._v

    def output(self, write, indent=0, strip=0):
        if self.id:
            id = ' id="%s"' % self.id
        else:
            id = ''

        name = self.__class__.__name__.lower()
        write(
            '%s<%s%s>%s</%s>' % (
            ' '*indent, name, id, self.value(), name)
            )
        if not strip:
            write('\n')

class Int(Scalar):
    pass

class Long(Scalar):

    def value(self):
        result = str(self._v)
        return result

class Float(Scalar):

    def value(self):
        return `self._v`


_binary_char = re.compile("[^\n\t\r -\x7e]").search

class String(Scalar):

    def __init__(self, v, encoding=''):
        encoding, v = self.convert(v)
        self.encoding = encoding
        Scalar.__init__(self, v)

    def convert(self, string):
        """Convert a string to a form that can be included in XML text"""
        if _binary_char(string):
            string = base64.encodestring(string)[:-1]
            return 'base64', string

        return _convert_sub(string)

    def output(self, write, indent=0, strip=0):
        if self.id:
            id = ' id="%s"' % self.id
        else:
            id = ''

        encoding = getattr(self, 'encoding', '')
        if encoding:
            encoding = ' encoding="%s"' % encoding
        else:
            encoding = ''

        name = self.__class__.__name__.lower()

        write('%s<%s%s%s>' % (' '*indent, name, id, encoding))
        write(self.value())
        write('</%s>' % name)
        if not strip:
            write('\n')


# TODO: use of a regular expression here seems to be brittle
# due to fuzzy semantics of unicode "surrogates".
# Eventually, we should probably rewrite this as a C
# function.

_invalid_xml_char = re.compile(
    u'['
    u'\x00-\x08'
    u'\x0b-\x0c'
    u'\x0e-\x1f'

    # Hack to get around utf-8 encoding bug(?) for surogates.
    + unichr(0xd800)+u'-'+unichr(0xdfff) + # u'\ud800-\udfff'

    u'\ufffe\uffff'
    u']'
    ).search

class Unicode(String):

    def convert(self, string):

        if _invalid_xml_char(string):
            string = string.encode('utf-8')
            string = base64.encodestring(string)[:-1]
            return 'base64', string

        return _convert_sub(string.encode('utf-8'))


class Wrapper(Base):

    def __init__(self, v):
        self._v = v

    def value(self):
        return self._v

    def output_nonscalar(self, write, name, id, v, str_indent, indent):
        write('%s<%s%s>\n' % (str_indent, name, id))
        v.output(write, indent+2)
        write('%s</%s>\n' % (str_indent, name))

    def output(self, write, indent=0):
        if self.id:
            id = ' id="%s"' % self.id
        else:
            id = ''
        name = self.__class__.__name__.lower()
        v = self._v
        str_indent = ' '*indent
        if isinstance(v, Scalar):
            write('%s<%s%s> ' % (str_indent, name, id))
            v.output(write, strip=1)
            write(' </%s>\n' % name)
        else:
            return self.output_nonscalar(
                write, name, id, v, str_indent, indent)

class CloseWrapper(Wrapper):

    # TODO: This doesn't do what I want anymore because we can't strip v
    def _output_nonscalar(self, write, name, id, v, str_indent, indent):
        write('%s<%s%s> ' % (str_indent, name, id))
        v.output(write, indent+2)
        write(' </%s>\n' % name)

class Collection(Base):
    def value(self, write, indent):
        raise AttributeError('value')

    def output(self, write, indent=0):
        if self.id:
            id = ' id="%s"' % self.id
        else:
            id= ''

        name = self.__class__.__name__.lower()

        i=' '*indent

        if self:
            write('%s<%s%s>\n' % (i, name, id))
            self.value(write, indent+2)
            write('%s</%s>\n' % (i, name))
        else:
            write('%s<%s%s />\n' % (i, name, id))

class Key(Wrapper):
    pass

class Name(Wrapper):
    pass

class Value(Wrapper):
    pass

class Dictionary(Collection):
    key_name = 'key'
    item_name = 'item'
    key_class = Key

    def __init__(self):
        self._d = []

    def __len__(self):
        return len(self._d)

    def __setitem__(self, k, v):
        self._d.append((k,v))

    def value(self, write, indent):
        ind = ' '*indent
        ind4 = indent+4
        begin = '%s<%s>\n' % (ind, self.item_name)
        end = '%s</%s>\n' % (ind, self.item_name)
        for key, value in self._d:
            if (key.__class__ is String
                and not key.encoding
                and identifier(key.value())
                ):
                id = getattr(key, 'id', '')
                if id:
                    id = ' id="%s"' % id
                write('%s<%s %s="%s"%s>\n' %
                      (ind, self.item_name, self.key_name, key.value(), id))
                value.output(write, ind4)
                write(end)
            else:
                write(begin)
                ind2 = indent+2
                self.key_class(key).output(write, ind2)
                Value(value).output(write, ind2)
                write(end)

class Attributes(Dictionary):
    key_name = 'name'
    item_name = 'attribute'
    key_class = Name

    def __init__(self, dictionary):
        Dictionary.__init__(self)
        self.__dict__.update(dictionary.__dict__)


class Sequence(Collection):

    def __init__(self, v=None):
        if not v:
            v = []
        self._subs = v

    def __getitem__(self, i):
        return self._subs[i]

    def __len__(self):
        return len(self._subs)

    def append(self, v):
        self._subs.append(v)

    def extend(self, v):
        self._subs.extend(v)

    def value(self, write, indent):
        for v in self._subs:
            v.output(write, indent)

class List(Sequence):
    pass

class Tuple(Sequence):
    pass

class Klass(CloseWrapper):
    pass

class Arguments(CloseWrapper):
    pass

class State(CloseWrapper):
    pass

class Pickle(Wrapper):
    pass

class Persistent(Wrapper):
    pass

class NamedScalar(Scalar):
    def __init__(self, name):
        self.name = name

    def output(self, write, indent=0, strip=0):
        write("%s<%s/>" % (' '*indent, self.name))
        if not strip:
            write('\n')

none = NamedScalar("none")
true = NamedScalar("true")
false = NamedScalar("false")

class Reference(Scalar):

    def output(self, write, indent=0, strip=0):
        write('%s<reference id="%s"/>' % (' '*indent,self._v))
        if not strip:
            write('\n')

Get=Reference # Get is pickle name, but Reference is nicer name

class Object(Sequence):
    pass

class Classic_Object(Sequence):
    pass

class Initialized_Object(Sequence):

    def __init__(self, klass, args):
        self.klass = klass
        self.args = args
        Sequence.__init__(self, [Klass(klass), Arguments(args)])

    def __setstate__(self, v):
        self.state = v
        self.append(State(v))

    def output(self, write, indent=0):
        klass = self.klass
        args = self.args

        if (klass == _reconstructor_global and
            isinstance(args, Tuple) and
            len(args) == 3 and
            args[1] == _object_global and
            args[2] == none and
            isinstance(getattr(self, 'state', None), Dictionary)
            ):
            klass = args[0]
            return Object((Klass(klass),
                           Attributes(self.state),
                           )
                          ).output(write, indent)

        if (not args and
            isinstance(getattr(self, 'state', None), Dictionary)):
            # Common simple case we want to optimize
            return Classic_Object((self._subs[0],
                                   Attributes(self.state)
                                   )
                                  ).output(write, indent)

        return Sequence.output(self, write, indent)


class ToXMLUnpickler(Unpickler):

    def __init__(self, *args):
        Unpickler.__init__(self, *args)
        self.__put_objects = {}
        self.__get_info = {} # id and object
        self.__got = 0

    def load(self):
        return Pickle(Unpickler.load(self))

    dispatch = {}
    dispatch.update(Unpickler.dispatch)

    def persistent_load(self, v):
        return Persistent(v)

    def load_persid(self):
        pid = self.readline()[:-1]
        self.append(self.persistent_load(String(pid)))
    dispatch[PERSID] = load_persid

    def load_none(self):
        self.append(none)
    dispatch[NONE] = load_none

    if _bool_support:
        def load_false(self):
            self.append(false)
        dispatch[NEWFALSE] = load_false

        def load_true(self):
            self.append(true)
        dispatch[NEWTRUE] = load_true

    def load_int(self):
        s = self.readline()[:-1]
        i = int(s)
        if s[0] == "0":
            if i == 1:
                self.append(true)
                return
            elif i == 0 and s != "0": # s == "00"
                self.append(false)
                return
        self.append(Int(i))
    dispatch[INT] = load_int

    def load_binint(self):
        self.append(Int(mloads('i' + self.read(4))))
    dispatch[BININT] = load_binint

    def load_binint1(self):
        self.append(Int(mloads('i' + self.read(1) + '\000\000\000')))
    dispatch[BININT1] = load_binint1

    def load_binint2(self):
        self.append(Int(mloads('i' + self.read(2) + '\000\000')))
    dispatch[BININT2] = load_binint2

    def load_long(self):
        self.append(Long(long(self.readline()[:-1], 0)))
    dispatch[LONG] = load_long

    def load_float(self):
        self.append(Float(float(self.readline()[:-1])))
    dispatch[FLOAT] = load_float

    def load_binfloat(self, unpack=struct.unpack):
        self.append(Float(unpack('>d', self.read(8))[0]))
    dispatch[BINFLOAT] = load_binfloat

    def load_string(self):
        self.append(String(eval(self.readline()[:-1],
                                {'__builtins__': {}}))) # Let's be careful
    dispatch[STRING] = load_string

    def load_binstring(self):
        len = mloads('i' + self.read(4))
        self.append(String(self.read(len)))
    dispatch[BINSTRING] = load_binstring

    def load_short_binstring(self):
        len = mloads('i' + self.read(1) + '\000\000\000')
        self.append(String(self.read(len)))
    dispatch[SHORT_BINSTRING] = load_short_binstring

    def load_unicode(self):
        self.append(Unicode(
            unicode(self.readline()[:-1],'raw-unicode-escape')
            ))
    dispatch[UNICODE] = load_unicode

    def load_binunicode(self):
        len = mloads('i' + self.read(4))
        self.append(Unicode(unicode(self.read(len),'utf-8')))
    dispatch[BINUNICODE] = load_binunicode

    def load_tuple(self):
        k = self.marker()
        self.stack[k:] = [Tuple(self.stack[k+1:])]
    dispatch[TUPLE] = load_tuple

    def load_empty_tuple(self):
        self.stack.append(Tuple())
    dispatch[EMPTY_TUPLE] = load_empty_tuple

    def load_empty_list(self):
        self.stack.append(List())
    dispatch[EMPTY_LIST] = load_empty_list

    def load_empty_dictionary(self):
        self.stack.append(Dictionary())
    dispatch[EMPTY_DICT] = load_empty_dictionary

    def load_list(self):
        k = self.marker()
        self.stack[k:] = [List(self.stack[k+1:])]
    dispatch[LIST] = load_list

    def load_dict(self):
        k = self.marker()
        d = Dictionary()
        items = self.stack[k+1:]
        for i in range(0, len(items), 2):
            key = items[i]
            value = items[i+1]
            d[key] = value
        self.stack[k:] = [d]
    dispatch[DICT] = load_dict

    def load_inst(self):
        k = self.marker()
        args = Tuple(self.stack[k+1:])
        del self.stack[k:]
        module = self.readline()[:-1]
        name = self.readline()[:-1]
        value = Initialized_Object(Global(module, name), args)
        self.append(value)
    dispatch[INST] = load_inst

    def load_obj(self):
        stack = self.stack
        k = self.marker()
        klass = stack[k + 1]
        del stack[k + 1]
        args = Tuple(stack[k + 1:])
        del stack[k:]
        value = Initialized_Object(klass,args)
        self.append(value)
    dispatch[OBJ] = load_obj

    def load_global(self):
        module = self.readline()[:-1]
        name = self.readline()[:-1]
        self.append(Global(module, name))
    dispatch[GLOBAL] = load_global

    def load_reduce(self):
        stack = self.stack

        callable = stack[-2]
        arg_tup  = stack[-1]
        del stack[-2:]

        value = Initialized_Object(callable, arg_tup)
        self.append(value)
    dispatch[REDUCE] = load_reduce

    idprefix = 'o'

    def __get(self, i):
        get_info = self.__get_info.get(i)
        if get_info is None:
            ob = self.__put_objects[i]
            if (ob.__class__ is String
                and not ob.encoding
                and identifier(ob.value())
                ):
                # We don't want this memoized
                get_id = None
            else:
                get_id = `self.__got`
                self.__got += 1
                ob.id = self.idprefix+get_id

            get_info = get_id, ob
            self.__get_info[i] = get_info

        else:
            get_id = get_info[0]

        if get_id is not None:
            # Normal case
            self.append(Get(self.idprefix+get_id))
        else:
            ob = get_info[1]
            self.append(ob)

    def __put(self, i):
        ob = self.stack[-1]
        self.__put_objects[i] = ob

    def load_get(self):
        i = self.readline()[:-1]
        self.__get(i)
    dispatch[GET] = load_get

    def load_binget(self):
        i = mloads('i' + self.read(1) + '\000\000\000')
        self.__get(`i`)
    dispatch[BINGET] = load_binget

    def load_long_binget(self):
        i = mloads('i' + self.read(4))
        self.__get(`i`)
    dispatch[LONG_BINGET] = load_long_binget

    def load_put(self):
        i = self.readline()[:-1]
        self.__put(i)
    dispatch[PUT] = load_put

    def load_binput(self):
        i = mloads('i' + self.read(1) + '\000\000\000')
        self.__put(`i`)
    dispatch[BINPUT] = load_binput

    def load_long_binput(self):
        i = mloads('i' + self.read(4))
        self.__put(`i`)
    dispatch[LONG_BINPUT] = load_long_binput


def ToXMLload(file):
    return ToXMLUnpickler(file).load()

def ToXMLloads(str):
    file = StringIO(str)
    return ToXMLUnpickler(file).load()

class xmlPickler(object):

    binary = 1

    def __init__(self):
        self._stack = []
        self._push([])

    def _push(self, top):
        self._stack.append(top)
        self._append = top.append

    def _pop(self):
        _stack = self._stack
        top = _stack.pop()
        self._append = _stack[-1].append
        return top

    def handle_starttag(self, tag, attrs):

        # Convert attrs to dict, if necessary
        if type(attrs) is list:
            x=0
            temp={}
            while x<len(attrs):
                temp[attrs[x]]=attrs[x+1]
                x=x+2
            attrs=temp

        self._push([tag, attrs])

    def handle_endtag(self, tag):
        top = self._pop()

        if tag == 'global':
            top = self.global_(tag, top)
        else:
            try:
                m = getattr(self, tag)
            except AttributeError:
                try: tag = tag.encode('us-ascii')
                except: pass
                raise ValueError(
                    "unrecognized element in XML pickle: %r" % tag)
            else:
                top = m(tag, top)

        self._append(top)

    def handle_data(self, data):
        if data.strip() or (self._stack[-1][0] in ('string', 'unicode')):
            self._append(data)

    def get_value(self):
        for s in self._stack[0][0]:
            if type(s) is unicode:
                print self._stack[0][0]
        return ''.join(self._stack[0][0])


    def pickle(self, tag, data, STOP_tuple = (STOP, )):
        v = data[2]
        if type(v) is list:
            v.append(STOP)
        else:
            v += STOP_tuple

        return v

    def none(self, tag, data, NONE_tuple = (NONE, )):
        return NONE_tuple

    def true(self, tag, data):
        return TRUE,

    def false(self, tag, data):
        return FALSE,

    def long(self, tag, data):
        return ((LONG + ''.join(data[2:]).strip().encode('ascii') + 'L\n'), )

    def save_wrapper(self, tag, data):
        return data[2]

    arguments = value = key = name = klass = state = save_wrapper

    def persis(self, tag, data):
        v = tuple(data[2])

        if  self.binary:
            return v + (BINPERSID, )
        else:
            return (PERSID, ) + v

    def persistent(self, tag, data):
        v = tuple(data[2])
        if  self.binary:
            return v + (BINPERSID, )
        else:
            return (PERSID, ) + v


    def int(self, tag, data):

        object = ''.join(data[2:]).strip()

        if self.binary:
            object = int(object)

            # If the int is small enough to fit in a signed 4-byte 2's-comp
            # format, we can store it more efficiently than the general
            # case.
            high_bits = object >> 31  # note that Python shift sign-extends
            if  high_bits == 0 or high_bits == -1:
                # All high bits are copies of bit 2**31, so the value
                # fits in a 4-byte signed int.
                i = mdumps(object)[1:]
                assert len(i) == 4
                if i[-2:] == '\000\000':    # fits in 2-byte unsigned int
                    if i[-3] == '\000':     # fits in 1-byte unsigned int
                        return (BININT1, i[0])
                    else:
                        return (BININT2, i[:2])
                else:
                    return (BININT, i)

        # Text pickle, or int too big to fit in signed 4-byte format.
        return (INT, object, '\n')

    def float(self, tag, data):
        v = ''.join(data[2:]).strip().encode('ascii')

        if self.binary:
            return BINFLOAT, struct.pack('>d',float(v))
        else:
            return FLOAT,  v, '\n'

    def _string(self, v, attrs):

        if self.binary:
            l = len(v)
            s = mdumps(l)[1:]
            if (l<256):
                v = SHORT_BINSTRING, s[0], v
            else:
                v = BINSTRING, s, v

        else:
            v = STRING, `v`, "\n"

        return self.put(v, attrs)

    def string(self, tag, data):
        v = ''.join(data[2:]).encode('ascii')
        attrs = data[1]
        encoding = attrs.get('encoding')
        if encoding:
            v = unconvert_string(encoding, v)

        return self._string(v, attrs)

    def unicode(self, tag, data):
        v = ''.join(data[2:]).encode('utf-8')
        attrs = data[1]

        encoding = attrs.get('encoding')
        if encoding:
            v = unconvert_unicode(encoding, v)

        if self.binary:
            # v = v.encode('utf-8')
            l = len(v)
            s = mdumps(l)[1:]
            v = (BINUNICODE, s, v)
        else:
            v = unicode(v, 'utf-8')
            v = v.replace("\\", "\\u005c")
            v = v.replace("\n", "\\u000a")
            v = (UNICODE, v.encode('raw-unicode-escape'), '\n')

        return self.put(v, attrs)

    def tuple(self, tag, data):
        T = data[2:]

        if not T:
            return (EMPTY_TUPLE, )

        v = [MARK]
        for x in T:
            v.extend(x)

        v.append(TUPLE)

        return self.put(v, data[1])

    def list(self, tag, data, EMPTY_LIST_tuple = (EMPTY_LIST, )):
        L = data[2:]
        attrs = data[1]
        v = []
        if self.binary:
            v.extend(self.put(EMPTY_LIST_tuple, attrs))
            if L:
                v.append(MARK)
                for x in L:
                    v.extend(x)
                v.append(APPENDS)
        else:
            v.extend(self.put((MARK, LIST), attrs))
            for x in L:
                v.extend(x)
                v.append(APPEND)

        return v

    def put(self, v, attrs):
        """Add a PUT command, if necessary.

        If v is a list, then the PUT is added to the list and the list
        is returned.
        """

        id = attrs.get('id', '').encode('ascii')

        if id:
            prefix = id.rfind('.')
            if prefix >= 0:
                id=id[prefix+1:]
            elif id[0] in 'io':
                id=id[1:]

            if self.binary:
                id=int(id)
                s=mdumps(id)[1:]
                if (id < 256):
                    id=s[0]
                    put = BINPUT
                else:
                    id=s
                    put= LONG_BINPUT
                id=put+id
            else:
                id=PUT+id+"\012"

            if type(v) is list:
                v.append(id)
            else:
                v = v + (id, )

        return v

    def dictionary(self, tag, data, EMPTY_DICT_tuple = (EMPTY_DICT, )):

        D = data[2:]
        v = []

        if self.binary:
            v.extend(self.put(EMPTY_DICT_tuple, data[1]))
            if D:
                v.append(MARK)
                for x in D:
                    v.extend(x)
                v.append(SETITEMS)
        else:
            v.extend(self.put((MARK, DICT), data[1]))
            for x in D:
                v.extend(x)
                v.append(SETITEM)

        return v

    attributes = dictionary

    def reference(self, tag, data):
        attrs = data[1]
        id = attrs['id'].encode('ascii')

        prefix = id.rfind('.')
        if prefix >= 0:
            id = id[prefix+1:]
        elif id[0] in 'oi':
            id = id[1:]

        get = GET

        if self.binary:
            id=int(id)
            s=mdumps(id)[1:]
            if (id < 256):
                id=s[0]
                get = BINGET
            else:
                id = s
                get = LONG_BINGET
            v=get+id
        else:
            v=get+id+'\n'

        return (v, )

    def initialized_object(self, tag, data):
        args_pickle = data[3]

        v = [MARK]
        v.extend(data[2])

        if args_pickle != (EMPTY_TUPLE, ):
            v.extend(args_pickle[1:-1])

        v.append(OBJ)

        v = self.put(v, data[1])

        if len(data) > 4:
            v.extend(data[4])
            v.append(BUILD)

        return v

    def object(self, tag, data):
        v = ['(ccopy_reg\n_reconstructor\n']
        v.extend(data[2])
        v.append('c__builtin__\nobject\nN')
        v.append(OBJ)

        v = self.put(v, data[1])
        v.extend(data[3])
        v.append(BUILD)

        return v

    def classic_object(self, tag, data):
        v = [MARK]
        v.extend(data[2])
        v.append(OBJ)

        v = self.put(v, data[1])
        v.extend(data[3])
        v.append(BUILD)

        return v

    def global_(self, tag, data):
        attrs=data[1]
        module = attrs['module'].encode('ascii')
        name = attrs['name'].encode('ascii')

        return self.put((GLOBAL, module, '\n', name, '\n'), attrs)

    def item(self, tag, data, key_name = 'key'):
        attrs = data[1]
        if key_name in attrs:
            assert len(data) == 3
            key = attrs[key_name].encode('ascii')
            key = self._string(key, attrs)
            value = data[2]

            if type(value) is list:
                value[0:0] = list(key)
            else:
                value = tuple(key) + value

            return value

        else:
            assert len(data) == 4
            key = data[2]
            if type(key) is not list:
                key = list(key)
            key.extend(data[3])

            return key

    def attribute(self, tag, data):
        return self.item(tag, data, 'name')
