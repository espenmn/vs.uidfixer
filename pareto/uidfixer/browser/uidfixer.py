from Products.ATContentTypes.content import base

from plone.portlets.interfaces import (
    IPortletManager, IPortletAssignmentMapping, IPortletRetriever,
    ILocalPortletAssignable)
from zope.component import getUtility, getMultiAdapter, ComponentLookupError

from Products.Five import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile

from plone.app.redirector.interfaces import IRedirectionStorage

from pareto.uidfixer import uidfixer


class UIDFixerView(BrowserView):
    template = ViewPageTemplateFile('uidfixer.pt')
    results_template = ViewPageTemplateFile('uidfixer-results.pt')

    def __call__(self):
        redirector = getUtility(IRedirectionStorage)
        self.fixer = uidfixer.UIDFixer(redirector)
        if not self.request.get('submit'):
            return self.template()
        return self.results_template()

    def results(self):
        """ return a nicely formatted list of objects for a template """
        portal_catalog = self.context.portal_catalog
        return [{
            'object': context,
            'field': field,
            'href': href,
            'resolved': not not uid,
            'resolved_url':
                (uid and
                    portal_catalog(UID=uid)[0].getObject().absolute_url()),
        } for context, field, href, uid in self.fix(self.context)]

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
            try:
                manager = getUtility(IPortletManager, manager_name, context)
            except ComponentLookupError:
                continue
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
                        html, results = self.fixer.replace_uids(html, context)
                        for href, uid in results:
                            if uid:
                                fixed = True
                            yield (context, portlet, href, uid)
                        if fixed and not self.request.get('dry'):
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
            html, results = self.fixer.replace_uids(html, context)
            for href, uid in results:
                if uid:
                    fixed = True
                yield context, field, href, uid
            if fixed and not self.request.get('dry'):
                field.set(context, html)
