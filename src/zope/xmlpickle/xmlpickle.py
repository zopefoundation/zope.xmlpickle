##############################################################################
#
# Copyright (c) 2002 Zope Corporation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################
"""Pickle-based serialization of Python objects to and from XML.

$Id$
"""

from xml.parsers import expat
from cStringIO import StringIO
from cPickle import loads as _standard_pickle_loads
from pickle import \
     Pickler as _StandardPickler, \
     MARK as _MARK, \
     EMPTY_DICT as _EMPTY_DICT, \
     DICT as _DICT, \
     SETITEM as _SETITEM, \
     SETITEMS as _SETITEMS

from zope.xmlpickle import ppml

class _PicklerThatSortsDictItems(_StandardPickler):
    dispatch = {}
    dispatch.update(_StandardPickler.dispatch)

    def save_dict(self, object):
        d = id(object)

        write = self.write
        save  = self.save
        memo  = self.memo

        if self.bin:
            write(_EMPTY_DICT)
        else:
            write(_MARK + _DICT)

        memo_len = len(memo)
        self.write(self.put(memo_len))
        memo[d] = (memo_len, object)

        using_setitems = (self.bin and (len(object) > 1))

        if using_setitems:
            write(_MARK)

        items = object.items()
        items.sort()
        for key, value in items:
            save(key)
            save(value)

            if not using_setitems:
                write(_SETITEM)

        if using_setitems:
            write(_SETITEMS)

    dispatch[dict] = save_dict

def _dumpsUsing_PicklerThatSortsDictItems(object, bin = 0):
    file = StringIO()
    _PicklerThatSortsDictItems(file, bin).dump(object)
    return file.getvalue()

def toxml(p, index=0):
    """Convert a standard Python pickle to xml

    You can provide a pickle string and get XML of an individual pickle:

    >>> import pickle
    >>> s = pickle.dumps(42)
    >>> print toxml(s).strip()
    <?xml version="1.0" encoding="utf-8" ?>
    <pickle> <int>42</int> </pickle>

    If the string contains multiple pickles:

    >>> l = [1]
    >>> import StringIO
    >>> f = StringIO.StringIO()
    >>> pickler = pickle.Pickler(f)
    >>> pickler.dump(l)
    >>> pickler.dump(42)
    >>> pickler.dump([42, l])
    >>> s = f.getvalue()

    You can supply indexes to access individual pickles:
    
    >>> print toxml(s).strip()
    <?xml version="1.0" encoding="utf-8" ?>
    <pickle>
      <list>
        <int>1</int>
      </list>
    </pickle>

    >>> print toxml(s, 0).strip()
    <?xml version="1.0" encoding="utf-8" ?>
    <pickle>
      <list>
        <int>1</int>
      </list>
    </pickle>

    >>> print toxml(s, 1).strip()
    <?xml version="1.0" encoding="utf-8" ?>
    <pickle> <int>42</int> </pickle>

    >>> print toxml(s, 2).strip()
    <?xml version="1.0" encoding="utf-8" ?>
    <pickle>
      <list>
        <int>42</int>
        <reference id="o0"/>
      </list>
    </pickle>

    Note that all of the pickles in a string share a common memo, so
    the last pickle in the example above has a reference to the
    list pickled in the first pickle.

    """
    u = ppml.ToXMLUnpickler(StringIO(p))
    while index > 0:
        xmlob = u.load()
        index -= 1
    xmlob = u.load()
    r = ['<?xml version="1.0" encoding="utf-8" ?>\n']
    xmlob.output(r.append)
    return ''.join(r)
    
def dumps(ob):
    """Serialize an object to XML
    """
    p = _dumpsUsing_PicklerThatSortsDictItems(ob, 1)
    return toxml(p)

def fromxml(xml):
    """Convert xml to a standard Python pickle
    """
    handler = ppml.xmlPickler()
    parser = expat.ParserCreate()
    parser.CharacterDataHandler = handler.handle_data
    parser.StartElementHandler = handler.handle_starttag
    parser.EndElementHandler = handler.handle_endtag
    parser.Parse(xml)
    pickle = handler.get_value()
    pickle = str(pickle)
    return pickle

def loads(xml):
    """Create an object from serialized XML
    """
    pickle = fromxml(xml)
    ob = _standard_pickle_loads(pickle)
    return ob
