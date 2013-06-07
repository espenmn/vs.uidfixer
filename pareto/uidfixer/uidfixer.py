import re
import urllib
from urlparse import urlparse


class UIDFixer(object):
    def __init__(self, redirector, site_root):
        self.redirector = redirector
        self.site_root = site_root

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
            if not href:
                continue
            scheme, netloc, path, params, query, fragment = urlparse(href)
            if not netloc and not href.startswith('resolveuid/'):
                # relative link, convert to resolveuid one
                uid = self.convert_link(href, context)
                yield href, uid, rest

    def convert_link(self, href, context):
        if '/resolveuid/' in href:
            _, uid = href.split('/resolveuid/')
            return uid
        else:
            try:
                context = self.resolve_redirector(href, context)
            except (KeyError, AttributeError), e:
                pass
            else:
                return context.UID()

    def resolve_redirector(self, href, context):
        if href.startswith('/'):
            # start from site root
            context = self.site_root
            href = href[1:]
        if href.endswith('/'):
            href = href[:-1]
        chunks = [urllib.unquote(chunk) for chunk in href.split('/')]
        while chunks:
            chunk = chunks[0]
            if chunk in ('', '.'):
                chunks.pop(0)
                continue
            elif chunk == '..':
                chunks.pop(0)
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
