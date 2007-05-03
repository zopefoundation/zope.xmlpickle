##############################################################################
#
# Copyright (c) 2001, 2002 Zope Corporation and Contributors.
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
"""Tests of xmlpickle package

$Id$
"""
import pickle
import unittest
from zope.xmlpickle import dumps, loads

class Test(unittest.TestCase):

    def __test(self, v, expected_xml=None):
        xml = dumps(v)
        if expected_xml:
            self.assertEqual(xml, expected_xml)
        newv = loads(xml)
        self.assertEqual(newv, v)

    def test_float(self):
        for v in (
            -2000000000.0, -70000.0, -30000.0, -3000.0, -100.0, -99.0, -1.0,
            0.0, 1.0, 99.0, 100.0, 3000.0, 30000.0, 70000.0, 2000000000.0,
            -1.2345678901234567e+308,
            -1.2345678901234567e+30,
            -12345678901234567.,
            -1234567890123456.7,
            -123456789012345.67,
            -12345678901234.567,
            -1234567890123.4567,
            -123456789012.34567,
            -12345678901.234567,
            -1234567890.1234567,
            -123456789.01234567,
            -12345678.901234567,
            -1234567.8901234567,
            -123456.78901234567,
            -12345.678901234567,
            -1234.5678901234567,
            -123.45678901234567,
            -12.345678901234567,
            -1.2345678901234567,
            -.12345678901234567,
            1.2345678901234567e+308,
            1.2345678901234567e+30,
            12345678901234567.,
            1234567890123456.7,
            123456789012345.67,
            12345678901234.567,
            1234567890123.4567,
            123456789012.34567,
            12345678901.234567,
            1234567890.1234567,
            123456789.01234567,
            12345678.901234567,
            1234567.8901234567,
            123456.78901234567,
            12345.678901234567,
            1234.5678901234567,
            123.45678901234567,
            12.345678901234567,
            1.2345678901234567,
            .12345678901234567,
            ):
            self.__test(v)

    def test_int(self):
        for v in (-2000000000, -70000, -30000, -3000, -100, -99, -1,
                  0, 1, 99, 100, 3000, 30000, 70000, 2000000000):
            self.__test(v)

    def test_long(self):
        for v in (-2000000000l, -70000l, -30000l, -3000l, -100l, -99l, -1l,
                  0l, 1l, 99l, 100l, 3000l, 30000l, 70000l, 2000000000l):
            self.__test(v)
        for i in range(10, 3000, 200):
            v = 30l**i
            self.__test(v)
            self.__test(-v)

    def test_None(self):
        self.__test(None,
                    '<?xml version="1.0" encoding="utf-8" ?>\n'
                    '<pickle> <none/> </pickle>\n'
                    )

    def test_True(self):
        self.__test(True)
        self.assertEqual(loads('<pickle><true/></pickle>'), True)

    def test_False(self):
        self.__test(False)
        self.assertEqual(loads('<pickle><false/></pickle>'), False)

    def test_reduce(self):
        v = DictSub()
        v['spam'] = 1.23
        v['eggs'] = 0
        v.name = 'v'
        self.__test(v)

    def test_string(self):
        self.__test('hello\n\tworld',
                    '<?xml version="1.0" encoding="utf-8" ?>\n'
                    '<pickle> <string>hello\n'
                    '\tworld</string> </pickle>\n'
                    )
        self.__test('hello\r\nworld',
                    '<?xml version="1.0" encoding="utf-8" ?>\n'
                    '<pickle> <string>hello&#x0d;\nworld</string> </pickle>\n'
                    )
        self.__test('hello\0\nworld',
                    '<?xml version="1.0" encoding="utf-8" ?>\n'
                    '<pickle> '
                    '<string encoding="base64">aGVsbG8ACndvcmxk</string>'
                    ' </pickle>\n'
                    )

        v = ''.join(map(chr, range(256)))
        self.__test(v[:-2])
        self.__test(v * 10)
        self.__test(v * 400)
        self.__test(v * 4000)

    def test_unicode(self):
        self.__test(
            u'hello\n\tworld',
            '<?xml version="1.0" encoding="utf-8" ?>\n'
            '<pickle> <unicode>hello\n'
            '\tworld</unicode> </pickle>\n'
            )
        self.__test(
            u'hello\r\nworld',
            '<?xml version="1.0" encoding="utf-8" ?>\n'
            '<pickle> <unicode>hello&#x0d;\nworld</unicode> </pickle>\n'
            )
        self.__test(
            u'hello\0\nworld\n',
            '<?xml version="1.0" encoding="utf-8" ?>\n<pickle> '
            '<unicode encoding="base64">aGVsbG8ACndvcmxkCg==</unicode>'
            ' </pickle>\n'
            )
        self.__test(
            u'hello\ufffe\nworld\n',
            '<?xml version="1.0" encoding="utf-8" ?>\n<pickle> '
            '<unicode encoding="base64">aGVsbG/vv74Kd29ybGQK</unicode>'
            ' </pickle>\n'
            )
        self.__test(
            u'Hello\ud7ff\nworld\n',
            '<?xml version="1.0" encoding="utf-8" ?>\n<pickle> '
            '<unicode>Hello\xed\x9f\xbf\nworld\n</unicode>'
            ' </pickle>\n'
            )

    def test_simple_object(self):
        expect = """\
<?xml version="1.0" encoding="utf-8" ?>
<pickle>
  <%sobject>
    <klass>
      <global name="%s" module="%s"/>
    </klass>
    <attributes>
      <attribute name="eggs">
          <int>2</int>
      </attribute>
      <attribute name="spam">
          <int>1</int>
      </attribute>
    </attributes>
  </%sobject>
</pickle>
"""

        self.__test(Simple(1,2),
                    expect % ('classic_', 'Simple', __name__, 'classic_'))
        self.__test(newSimple(1,2),
                    expect % ('', 'newSimple', __name__, ''))
        self.__test(newSimple(1,2))

    def test_object_w_funny_state(self):
        o = Simple(1,2)
        o.__dict__[(5,6,7)] = None
        self.__test(o)
        o = newSimple(1,2)
        o.__dict__[(5,6,7)] = None
        self.__test(o)

    def test_object_w_initial_args(self):
        o = WInitial([1,2,3], None)
        o.foo = 'bar'
        self.__test(o)
        o = newWInitial([1,2,3], None)
        o.foo = 'bar'
        self.__test(o)

    def test_dict(self):
        self.__test({})
        self.__test({1.23: u'foo', 'spam': [123]})
        d = {}
        for i in range(1000):
            d[i] = str(i*i)
        self.__test(d)

    def test_complex(self):
        self.__test(complex(1,2))

    def test_cycles(self):
        # Python 2.4 does not support recursive comparisons to the
        # same extent as Python 2.3, so we test these recursive
        # structures by comparing the standard pickles of the original
        # and pickled/unpickled copy.  This works for things like
        # lists and tuples, but could easily break for dictionaries.

        l = [1, 2 , 3]
        l.append(l)
        xml = dumps(l)
        newl = loads(xml)
        p1 = pickle.dumps(l)
        p2 = pickle.dumps(newl)
        self.assertEqual(p1, p2)

        t = l, l
        l.append(t)
        xml = dumps(l)
        newl = loads(xml)
        p1 = pickle.dumps(l)
        p2 = pickle.dumps(newl)
        self.assertEqual(p1, p2)

    def test_list(self):
        self.__test([])
        self.__test([1,2,3])
        self.__test(range(1000))

    def test_tuple(self):
        self.__test(())
        self.__test((1,2,3))


class Simple:
    """This class is expected to be a classic class."""
    
    def __init__(self, *a):
        self.spam, self.eggs = a

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return '%s %r' % (self.__class__.__name__, self.__dict__)

class WInitial(Simple):
    def __getinitargs__(self):
        return self.spam, self.eggs

class newSimple(Simple, object): pass
class newWInitial(WInitial, object): pass

class DictSub(dict):
    def __eq__(self, other):
        items = self.items()
        items.sort()
        otems = other.items()
        otems.sort()
        return (items, self.__dict__) == (otems, other.__dict__)

    def __ne__(self, other):
        return not self.__eq__(other)

def test_suite():
    from zope.testing.doctestunit import DocTestSuite
    return unittest.TestSuite((
        unittest.makeSuite(Test),
        DocTestSuite('zope.xmlpickle.xmlpickle'),
        ))

if __name__=='__main__':
    unittest.main(defaultTest='test_suite')
