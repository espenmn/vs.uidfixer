import unittest

import uidfixer


class FakeObjectNoUID(object):
    isPrincipiaFolderish = False

    def __init__(self, id, parent=None):
        self.id = id
        self.aq_parent = parent
        if parent is not None:
            parent.isPrincipiaFolderish = True
            parent.children[id] = self
        self.children = {}

    def __getitem__(self, name):
        return self.children[name]

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    def restrictedTraverse(self, path):
        current = self
        if path[0] == '':
            current = self.root
            path.pop(0)
        while path:
            current = current[path.pop(0)]
        return current

    def getPhysicalPath(self):
        if self.aq_parent is None:
            return ('',)
        path = self.aq_parent.getPhysicalPath()
        path = path + (self.id,)
        return path

    @property
    def root(self):
        if self.aq_parent is not None:
            return self.aq_parent.root
        return self

    # mimic a view a bit
    def view(self):
        pass


class FakeObject(FakeObjectNoUID):
    def __init__(self, id, uid, parent=None):
        self.id = id
        self.uid = uid
        self.aq_parent = parent
        if parent is not None:
            parent.isPrincipiaFolderish = True
            parent.children[id] = self
        self.children = {}

    def UID(self):
        return self.uid


class UIDFixerForTests(uidfixer.UIDFixer):
    def verify_uid(self, uid, context):
        return True


class HrefProcessorTestCase(unittest.TestCase):
    def setUp(self):
        # NOTE: isPrincipiaFolderish is set to True if an object gets
        # children assigned, so it's False for all leaf-nodes (this is
        # used when paths are resolved, on non-folders the start context
        # of path resolution is the parent, not the item)
        self.redirector = redirector = {}
        self.root = root = FakeObject('root', '0')
        self.root.isPrincipiaFolderish = True
        self.fixer = UIDFixerForTests(redirector, root, ['example.com'])
        self.foo = foo = FakeObject('foo', '1', root)
        self.bar = FakeObject('bar', '2', foo)
        self.spam = FakeObject('spam', '3', root)
        self.nouid = FakeObjectNoUID('nouid', root)

    def test_nofix(self):
        htmlres, results = self.fixer.replace_uids(
            '<a href="resolveuid/0">root</a>', self.root)
        self.assertEquals(htmlres, '<a href="resolveuid/0">root</a>')
        self.assertEquals(len(results), 0)

    def test_self(self):
        htmlres, results = self.fixer.replace_uids(
            '<a href=".">root</a>', self.root)
        self.assertEquals(htmlres, '<a href="resolveuid/0">root</a>')

    def test_parent(self):
        htmlres, results = self.fixer.replace_uids(
            '<a href="..">root</a>', self.foo)
        self.assertEquals(htmlres, '<a href="resolveuid/0">root</a>')

    def test_root(self):
        htmlres, results = self.fixer.replace_uids(
            '<a href="/">root</a>', self.foo)
        self.assertEquals(htmlres, '<a href="resolveuid/0">root</a>')

    def test_weird_routing(self):
        htmlres, results = self.fixer.replace_uids(
            '<a href="./foo/bar/.././bar/../.">foo</a>', self.spam)
        self.assertEquals(htmlres, '<a href="resolveuid/1">foo</a>')

    def test_absolute(self):
        htmlres, results = self.fixer.replace_uids(
            '<a href="/spam">spam</a>', self.foo)
        self.assertEquals(htmlres, '<a href="resolveuid/3">spam</a>')

    def test_hash(self):
        html = '<a href="bar#bar">bar</a><a href="/spam#baz">spam</a>'
        htmlres, results = self.fixer.replace_uids(html, self.foo)
        self.assertEquals(
            htmlres,
            '<a href="resolveuid/2#bar">bar</a>'
            '<a href="resolveuid/3#baz">spam</a>')

    def test_replace_unresolved(self):
        htmlres, results = self.fixer.replace_uids(
            '<a href="/eggs">eggs</a>', self.foo)
        self.assertEquals(htmlres, '<a href="/eggs">eggs</a>')
        self.assertEquals(len(results), 1)
        self.assertEquals(results[0][1], None)

    def test_multi(self):
        htmlres, results = self.fixer.replace_uids(
                '<a href="..">root</a><a href=".">foo</a>', self.foo)
        self.assertEquals(
            htmlres,
            '<a href="resolveuid/0">root</a><a href="resolveuid/1">foo</a>')

    def test_multi_reverse(self):
        html = '<a href=".">foo</a><a href="..">root</a>'
        htmlres, results = self.fixer.replace_uids(html, self.foo)
        self.assertEquals(
            htmlres,
            '<a href="resolveuid/1">foo</a><a href="resolveuid/0">root</a>')

    def test_multiple_hashes(self):
        html = '<a href="#foo">#foo</a><a href="#bar">#bar</a>'
        htmlres, results = self.fixer.replace_uids(html, self.foo)
        self.assertEquals(htmlres, html)

    def test_replace_redirector(self):
        self.redirector['/foo'] = '/spam'
        html = '<a href=".">spam</a>'
        htmlres, results = self.fixer.replace_uids(html, self.foo)
        self.assertEquals(htmlres, '<a href="resolveuid/3">spam</a>')

    def test_replace_redirector_long_path(self):
        self.redirector[
            '/downloads/organisatie-regelgeving/'
            'organisatie-regelgeving-lsp/20130215_VergoedingenLSP.pdf'
        ] = '/spam'
        html = (
            '<a href="./../downloads/organisatie-regelgeving/'
            'organisatie-regelgeving-lsp/20130215_VergoedingenLSP.pdf">'
            'spam</a>')
        htmlres, results = self.fixer.replace_uids(html, self.bar)
        self.assertEquals(htmlres, '<a href="resolveuid/3">spam</a>')

    def test_replace_broken_resolveuid(self):
        html = '<a href="/bla/foo/resolveuid/1">foo</a>'
        htmlres, results = self.fixer.replace_uids(html, self.spam)
        self.assertEquals(htmlres, '<a href="resolveuid/1">foo</a>')

    def test_replace_unresolvable_broken_resolveuid(self):
        html = '<a href="/bla/foo/resolveuid/123">borken</a>'
        htmlres, results = self.fixer.replace_uids(html, self.spam)
        self.assertEquals(htmlres, '<a href="resolveuid/123">borken</a>')

    def test_wrong_protocol(self):
        html = '<a href="mailto:foo@bar.baz">mail</a>'
        htmlres, results = self.fixer.replace_uids(html, self.spam)
        self.assertEquals(htmlres, '<a href="mailto:foo@bar.baz">mail</a>')
        self.assertEquals(len(results), 0)

    def test_absolute_url(self):
        htmlres, results = self.fixer.replace_uids(
            '<a href="http://example.com/">root</a>', self.root)
        self.assertEquals(htmlres, '<a href="resolveuid/0">root</a>')

    def test_absolute_url_no_uid(self):
        htmlres, results = self.fixer.replace_uids(
            '<a href="http://example.com/nouid">nouid</a>', self.root)
        self.assertEquals(
            htmlres, '<a href="http://example.com/nouid">nouid</a>')

    def test_absolute_url_with_method(self):
        htmlres, results = self.fixer.replace_uids(
            '<a href="http://example.com/view">root</a>', self.root)
        self.assertEquals(htmlres, '<a href="resolveuid/0/view">root</a>')


def test_suite():
    from zope.testing import doctestunit
    from zope.component import testing
    from Testing import ZopeTestCase as ztc
    return unittest.TestSuite([

        unittest.TestSuite([HrefProcessorTestCase]),

        # Unit tests for your API
        doctestunit.DocFileSuite(
            'README.txt', package='pareto.uidfixer',
            setUp=testing.setUp, tearDown=testing.tearDown),

        #doctestunit.DocTestSuite(
        #    module='pareto.uidfixer.mymodule',
        #    setUp=testing.setUp, tearDown=testing.tearDown),

        # Integration tests that use ZopeTestCase
        #ztc.ZopeDocFileSuite(
        #    'README.txt', package='pareto.uidfixer',
        #    setUp=testing.setUp, tearDown=testing.tearDown),

        #ztc.FunctionalDocFileSuite(
        #    'browser.txt', package='pareto.uidfixer'),

        ])

if __name__ == '__main__':
    unittest.main()
