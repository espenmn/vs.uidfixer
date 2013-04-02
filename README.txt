pareto.uidfixer
===============

Find relative links in a Plone site and replace them with 'resolveuid' ones.
This product finds all links that point to items within the site, or links
that contain 'resolveuid' as part of the URL, then uses traversal and the
redirection tool (portal_redirection) to get to the object linked to. If
that fails, the link is kept in-tact and is reported, if an object is found,
the link is converted to a proper 'resolveuid' one and saved.

Installation
------------

Simply add pareto.uidfixer to your buildout.cfg::

    eggs =
        ...
        pareto.uidfixer
    zcml =
        ...
        pareto.uidfixer
    auto-checkout =
        ...
        pareto.uidfixer

(where '...' are previously available entries, if any, if the sections don't
yet exist, create).

Then run buildout again, and the product should be added.

Basic usage
-----------

After running buildout, you can add '/@@uidfixer' behind any URL on the site to
fix the links on the object the URL points to, recursively (so all containing
objects will be fixed). Note that you will need to log in as administrator to
use the view. The view will present a 'fix' button, press it to get a list of
all fixed and all unfixable items, unfixable items (if any) are marked red.

Questions, remarks, etc.
------------------------

For questions, remarks, etc. send a mail to guido.wesdorp at pareto dot nl.
