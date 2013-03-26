import re
import urllib
from urlparse import urlparse

from Products.ATContentTypes.content import base

from plone.portlets.interfaces import (
    IPortletManager, IPortletAssignmentMapping, IPortletRetriever,
    ILocalPortletAssignable)
from zope.component import getUtility, getMultiAdapter, ComponentLookupError

from Products.Five import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile

from plone.app.redirector.interfaces import IRedirectionStorage

# XXX meh, no clue what lib has this anymore... replace once remembered!
def entitize(s):
    s = s.replace('&', '&amp;')
    s = s.replace('"', '&quot;')
    s = s.replace('<', '&lt;')
    s = s.replace('>', '&gt;')
    return s


class UIDFixerView(BrowserView):
    template = ViewPageTemplateFile('uidfixer.pt')
    results_template = ViewPageTemplateFile('uidfixer-results.pt')

    def __call__(self):
        if not self.request.get('submit'):
            return self.template()
        return self.results_template()

    def results(self):
        """ return a nicely formatted list of objects for a template """
        return [{
            'object': context,
            'field': field,
            'href': href,
            'resolved': resolved}
            for context, field, href, resolved in self.fix(self.context)]

    def fix(self, context, processed_portlets=None):
        if not context.getId().startswith('portal_'):
            if processed_portlets is None:
                processed_portlets = []
            if isinstance(context, base.ATCTContent):
                for info in self.process_content(context):
                    yield info
            # process portlets, both Plone ones and those from Collage
            for info in self.process_portlets(context, processed_portlets):
                yield info
            for item in context.objectValues():
                for info in self.fix(item, processed_portlets):
                    yield info

    def process_portlets(self, context, processed_portlets):
        for manager_name in (
                'plone.leftcolumn', 'plone.rightcolumn',
                'collage.portletmanager'):
            manager = getUtility(IPortletManager, manager_name, context)
            if manager:
                retriever = getMultiAdapter(
                    (context, manager), IPortletRetriever)
                for portlet in retriever.getPortlets():
                    assignment = portlet['assignment']
                    if assignment in processed_portlets:
                        continue
                    processed_portlets.append(assignment)
                    if hasattr(assignment, 'text'):
                        html = assignment.text
                        fixed = False
                        for href, uid in self.find_uids(html, context):
                            resolved = not not uid
                            if resolved:
                                html = html.replace(
                                    'href="%s"' % (href,),
                                    'href="resolveuid/%s"' % (uid,))
                                fixed = True
                            yield (
                                context, portlet,
                                href, resolved)
                        if fixed:
                            assignment.text = html
                            assignment._p_changed = True

    def process_content(self, context):
        fields = context.schema.fields()
        for field in fields:
            if (field.type != 'text' or
                    field.default_output_type != 'text/x-html-safe'):
                continue
            fieldname = field.getName()
            html = field.getRaw(context)
            fixed = False
            for href, uid in self.find_uids(html, context):
                resolved = not not uid
                if not resolved:
                    # html = html.replace(href, 'UNRESOLVED:/%s' % (uid,))
                    pass
                else:
                    html = html.replace(
                        'href="%s"' % (href,),
                        'href="resolveuid/%s"' % (uid,))
                fixed = True
                yield context, field, href, resolved
            if fixed:
                field.set(context, html)

    def convert_link(self, href, context):
        if '/resolveuid/' in href:
            _, uid = href.split('/resolveuid/')
            return uid
        else:
            try:
                context = self.resolve_redirector(href, context)
            except (KeyError, AttributeError):
                pass
            else:
                return context.UID()

    def resolve_redirector(self, href, context):
        redirector = getUtility(IRedirectionStorage)
        if '?' in href:
            href, _ = href.split('?')
        if href.endswith('/'):
            href = href[:-1]
        chunks = href.split('/')
        while chunks:
            chunk = urllib.unquote(chunks[0])
            if chunk in ('', '.'):
                chunks.pop(0)
                continue
            elif chunk == '..':
                chunks.pop(0)
                context = context.aq_parent
            else:
                break
        path = list(context.getPhysicalPath()) + chunks
        redirect = redirector.get('/'.join(path))
        if redirect is not None:
            redirected = context.restrictedTraverse(
                redirect.split('/'))
            if redirected is not None:
                context = redirected
            else:
                context = getattr(context, chunk)
        else:
            context = getattr(context, chunk)
        return context

    _reg_href = re.compile(r'href="([^"]+)"')
    def find_uids(self, html, context):
        while True:
            match = self._reg_href.search(html)
            if not match:
                break
            href = match.group(1)
            html = html.replace(match.group(0), '')
            scheme, netloc, path, params, query, fragment = urlparse(href)
            if not scheme and not href.startswith('resolveuid/'):
                # relative link, convert to resolveuid one
                uid = self.convert_link(href, context)
                yield href, uid
