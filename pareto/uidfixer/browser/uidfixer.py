from zope.component import getUtility
from Products.CMFCore.utils import getToolByName
from Products.Five.browser import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile

from plone.app.redirector.interfaces import IRedirectionStorage

from pareto.plonehtml import plonehtml
from .. import uidfixer


class UIDFixerView(BrowserView):
    template = ViewPageTemplateFile('uidfixer.pt')
    results_template = ViewPageTemplateFile('uidfixer-results.pt')

    def __call__(self):
        portal = getToolByName(self.context, "portal_url").getPortalObject()
        redirector = getUtility(IRedirectionStorage)
        self.fixer = uidfixer.UIDFixer(
            redirector, portal, ['www.knmp.nl', 'edit.knmp.nl', 'knmp.nl'])
        if not self.request.get('submit'):
            return self.template()
        return self.results_template()

    def results(self):
        """ return a nicely formatted list of objects for a template """
        return [{
            'object': context,
            'field': field,
            'href': href,
            'resolved': not not uid,
            'resolved_url': self._url_by_uid(uid, href),
        } for context, field, (href, uid) in self.fix(self.context)]

    def _url_by_uid(self, uid, href):
        portal_catalog = self.context.portal_catalog
        if not uid:
            return ''
        brains = portal_catalog(UID=uid)
        if not brains:
            import pdb; pdb.set_trace()
        return brains[0].getObject().absolute_url()

    def fix(self, context):
        processor = plonehtml.PloneHtmlProcessor(
            self._fixhandler, self.request.get('dry'))
        for info in processor.process(context):
            yield info

    def _fixhandler(self, html, context):
        html, results = self.fixer.replace_uids(html, context)
        # we know stuff has been fixed by checking if there's a uid (second
        # tuple element of the return value items)
        fixed = [x for x in results if x[1]]
        return html, results, not not fixed
