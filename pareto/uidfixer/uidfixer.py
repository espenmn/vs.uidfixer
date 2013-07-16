import re
import urllib
from urlparse import urlparse


class UIDFixer(object):
    def __init__(self, redirector, site_root, hostnames=None):
        self.redirector = redirector
        self.site_root = site_root
        self.hostnames = hostnames or []

    def replace_uids(self, html, context):
        results = []
        for href, uid, rest in self.find_uids(html, context):
            if uid:
                fro = 'href="%s%s"' % (href, rest)
                to = 'href="resolveuid/%s%s"' % (uid, rest)
                assert fro in html, 'href="%s%s"' % (href, rest)
                html = html.replace(fro, to)
            results.append((href, uid))
        return html, results

    _reg_href = re.compile(r'href="([^"]+)"')
    def find_uids(self, html, context):
        while True:
            match = self._reg_href.search(html)
            if not match:
                break
            href = match.group(1)
            # leave any views, GET vars and hashes alone
            # not entirely correct, but this seems
            # relatively solid
            rest = ''
            for s in ('@@', '?', '#', '++'):
                if s in href:
                    rest += href[href.find(s):]
                    href = href[:href.find(s)]
            html = html.replace(match.group(0), '')
            if not href or href.startswith('resolveuid/'):
                continue
            scheme, netloc, path, params, query, fragment = urlparse(href)
            if (not scheme or scheme in ('http', 'https') and
                    (not netloc or netloc in self.hostnames)):
                # relative link, convert to resolveuid one
                uid = self.convert_link(path, context)
                yield href, uid, rest

    def convert_link(self, href, context):
        if '/resolveuid/' in href:
            _, uid = href.split('/resolveuid/')
            # verify uid, if it doesn't exist anymore, we don't fix the link
            if not self.verify_uid(uid, context):
                return
            return uid
        else:
            try:
                context = self.resolve_redirector(href, context)
            except (KeyError, AttributeError), e:
                pass
            else:
                # Zope may return a callable rather than a proper object,
                # in which case we want to call it (it's a view)
                if hasattr(context, 'im_self'):
                    context = context.im_self
                    # HACK: add the view name to the uid to get the right
                    # urls later on ('resolveuid/<uid>/<view>')
                    if not hasattr(context, 'UID'):
                        print 'CAN NOT CONVERT NON-PLONE OBJECT HREF:', href
                        return
                    return '%s/%s' % (context.UID(), href.split('/')[-1])
                if not hasattr(context, 'UID'):
                    print 'CAN NOT CONVERT NON-PLONE OBJECT HREF:', href
                    return
                return context.UID()

    def resolve_redirector(self, href, context):
        if href.startswith('/'):
            # start from site root
            context = self.site_root
            href = href[1:]
        if len(href) > 1 and href.endswith('/'):
            href = href[:-1]
        # on non-folder types, the start context for hrefs is the parent
        # container (so, <base> tags on folders end on a slash, on non-folders
        # they don't)
        if not context.isPrincipiaFolderish:
            context = context.aq_parent
        chunks = [urllib.unquote(chunk) for chunk in href.split('/')]
        while chunks:
            chunk = chunks[0]
            if chunk in ('', '.'):
                chunks.pop(0)
                continue
            elif chunk == '..':
                chunks.pop(0)
                if context != self.site_root:
                    context = context.aq_parent
            else:
                break
        path = list(context.getPhysicalPath()) + chunks
        redirect = self.redirector.get('/'.join(path))
        if redirect is not None:
            redirected = context.restrictedTraverse(
                redirect.split('/'))
            if redirected is not None:
                context = redirected
            else:
                while chunks:
                    chunk = chunks.pop(0)
                    context = getattr(context, chunk)
        else:
            while chunks:
                chunk = chunks.pop(0)
                if chunk == '.':
                    continue
                elif chunk == '..':
                    context = context.aq_parent
                else:
                    context = getattr(context, chunk)
        return context

    def verify_uid(self, uid, context):
        return not not context.portal_catalog(UID=uid)
