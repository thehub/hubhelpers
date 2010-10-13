from django.http import HttpResponse, HttpRequest
from django.shortcuts import render_to_response
from django import forms
from django.contrib.formtools.wizard import FormWizard

import base64
import os
import mechanize
from mako.template import Template
import httpagentparser

import hubhelpers.settings as settings

try:
    import reporter.locations as locationsconf
    locations = locationsconf.LOCATION_CODES
    LOCATION_FIELD_HELP = locationsconf.LOCATION_FIELD_HELP
except Exception, err:
    print err
    LOCATION_FIELD_HELP = "Use 'Other' if you don't find your location in the list"
    locations = {} # form should still be rendered

class AboutYouAndRequestTypeForm(forms.Form):
    error_css_class = 'error'
    required_css_class = 'required'

    ticket_type = forms.ChoiceField(required=True, widget=forms.RadioSelect, label='What describes your request best?', initial='bug')
    ticket_type.choices = (
        ('bug', 'Report an issue. (like problem, requirement or feature request, mail address change, multiple mail address request)'),
        ('mailreq', 'Request a new mail address'),
    )
    project = forms.ChoiceField(label="Which area are you having problems with?", required=True, widget=forms.RadioSelect, help_text="Select area 'Hub Networks' if you are unsure", initial='networks')
    project.choices = (
        ('space', 'Hub Space (Invoicing, space booking, membership management)'),
        ('website', 'Hub Website (microsite, main website)'),
        ('plus', 'Hub Plus'),
        ('networks', 'Hub Networks (Mailing lists, e-mail, internet, security, printing)'),
        #('test', "Test project (Don't use for real issues)"),
        )

    mailreq_type = forms.ChoiceField(label="Mail Request Type", required=False, widget=forms.RadioSelect, initial='mailreq', help_text='Select default if you are unsure')
    mailreq_type.choices = (
        ('forward', 'Personal mail address as a simple forwarding'),
        ('personal', 'Personal mail address as IMAP/POP3 mailbox (staff only)'),
        ('pubcontact', 'Public contact address (e.g.  location (e.g.  location.hosts@the-hub.net).hosts@the-hub.net)'),
        ('ml', 'Mailing List  (e.g.  location.members@lists.the-hub.net)'),
        )

    global mailreq_choices
    mailreq_choices = mailreq_type.choices

    reporter = forms.CharField(label="Your Name")
    email = forms.EmailField(label="Your Email address", help_text="to update you about the progress")
    cc_email = forms.EmailField(label="Also notify", required=False, help_text="Do you want to add one more email to ticket notifications?")
    # as described at http://the-hub.pbworks.com/Hub%20three%20letter%20codes
    location = forms.ChoiceField(label="Which Hub is this ticket for?", help_text=LOCATION_FIELD_HELP, initial='other')
    location.choices = [('OTHER', 'Other')] + sorted(locations.items(), key=lambda item: item[1])

class CommonFields(object):
    pass
common_fields = CommonFields()
common_fields.summary = (forms.CharField, dict(max_length=100, required=True)) # TODO

class BugForm(forms.Form):
    summary = forms.CharField(label="Short summary of the problem", max_length=100, required=True)
    os = forms.CharField(label="Operating System", max_length=50, required=False)
    description = forms.CharField(widget=forms.widgets.Textarea, label="Please take us through, step by step, what happened before the error occurred. This will help us recreate what happened on our machines", required=False, help_text="eg.1) Click edit in Profile section \n 2) Change the fax no.")
    suggestion = forms.CharField(label="Do you have a suggested solution?", widget=forms.Textarea, required=False)
    url = forms.URLField(label='URL', required=False)
    browser = forms.CharField(max_length=50, required=False)

class NetworkTicketForm(forms.Form):
    summary = forms.CharField(label="Short summary of the problem", max_length=100, required=True)
    os = forms.CharField(label="Operating System", max_length=50, required=False)
    description = forms.CharField(widget=forms.widgets.Textarea, label="Please take us through, step by step, what happened before the error occurred. This will help us recreate what happened on our machines", required=False, help_text="eg.1) Click edit in Profile section \n 2) Change the fax no.")
    suggestion = forms.CharField(label="Do you have a suggested solution?", widget=forms.Textarea, required=False)

class MailRequestForm(forms.Form): pass

class MailRequest_Personal(MailRequestForm):
    lhs = forms.CharField(label='Requested Address', help_text='@the-hub.net', required=True)
    maillogin = forms.CharField(label='Requested mailbox login name', required=False)
    mobile = forms.CharField(label='A mobile phone number', help_text='where we can SMS the password to..', required=False)
    mailreqmoreinfo = forms.CharField(label='Additional information on this person/address/list', widget=forms.Textarea, required=False)
    #moremailreqs = forms.BooleanField(label='Have more email requests?', initial=False, required=False)

class MailRequest_Forward(MailRequestForm):
    lhs = forms.CharField(label='Requested Address', help_text='@the-hub.net', required=True)
    forward = forms.EmailField('forward', help_text="The mail address to which incoming mail should get forwarded to.", label="Existing Email Address", required=True)
    mailreqmoreinfo = forms.CharField(label='Additional information on this person/address/list', widget=forms.Textarea, required=False)
    #moremailreqs = forms.BooleanField(label='Have more email requests?', initial=False, required=False)

class MailRequest_ML(MailRequestForm):
    listlhs = forms.CharField(label="Requested Address", help_text="@lists.the-hub.net", required=True)
    mldescr = forms.CharField(label='One line description for the mailing list', required=False)
    mlsubjectprefix = forms.CharField(label='Tag prefixing the subject of each posting', required=False)
    mladmin = forms.EmailField(label="The mail addresses of the initial administrators/moderators for this mailing list", required=True)
    mlqueries = forms.EmailField(label="A contact mail address for questions from subscribers", required=False)

class MailRequest_Public(MailRequestForm):
    publhs = forms.CharField(label="Requested Address", help_text="@the-hub.net", required=True)
    forwards = forms.CharField(label="Addresses to forward the mails to public contact", required=True)

class AddCCsForm(forms.Form):
    cc_email = forms.EmailField(label="Also notify", required=False, help_text="Do you want to add one more email to ticket notifications?")

mailreq_forms = dict(personal = MailRequest_Personal, forward = MailRequest_Forward, ml = MailRequest_ML, pubcontact = MailRequest_Public)
mailreqmapping = dict((req, form().fields.keys()) for req, form in mailreq_forms.items())

def fieldvalue_in_step(step, data, name, safe=False):
    if safe:
        return data.get('-'.join((str(step), name)), None)
    return data['-'.join((str(step), name))]

def set_fieldvalue_in_step(step, data, name, value):
    name = '-'.join((str(step), name))
    if name in data:
        data[name] = value

class TicketWizard(FormWizard):
    def get_template(self, step):
        return "newticketwizard.html"
    def process_step(self, request, form, step):
        if step == 0:
            project_type = fieldvalue_in_step(step, form.data, 'project')
            ticket_type = fieldvalue_in_step(step, form.data, 'ticket_type')
            mailreq_type = fieldvalue_in_step(step, form.data, 'mailreq_type')
            if (project_type == 'networks'):
                if (ticket_type == 'mailreq'):
                    Form = mailreq_forms[mailreq_type]
                    form_index = self.form_list.index(MailRequestForm)
                    self.form_list[form_index] = Form
                else:
                    self.form_list[1] = NetworkTicketForm
            else:
                self.form_list[1] = BugForm
    def done(self, request, form_list):
        merged_dict = {}
        for form in form_list:
            merged_dict.update(form.cleaned_data)
        ticket_url = create(**merged_dict)
        return render_to_response('done.html', dict(ticket_url = ticket_url, reporter = merged_dict['reporter']))

def new(request):
    try:
        initial = {0: dict( zip(("first_name", "last_name", "location", "email"), base64.b64decode(request.COOKIES['uinfo']).split("|")))}
        initial[0]['reporter'] = "%(first_name)s %(last_name)s" % initial[0]
        initial[0]['location'] = locationsconf.LOCATION_CODES2.get(initial[0]['location'], 'OTHER')
        del initial[0]['first_name']
        del initial[0]['last_name']
    except Exception, err:
        print err
        initial = {}
    try:
        agent_info = httpagentparser.detect(request.META['HTTP_USER_AGENT'])
    except Exception, err:
        print err
        agent_info = {}
    os_info = dict(name='', version='')
    os_info.update(agent_info.get('os', {}))
    os_info.update(agent_info.get('flavor', {}))
    os_info.update(agent_info.get('dist', {}))
    os_info_s = "%(name)s %(version)s" % os_info

    br_info = dict(name='', version='')
    br_info.update(agent_info.get('browser', {}))
    br_info_s = "%(name)s %(version)s" % br_info

    initial[1] = dict(os=os_info_s, browser=br_info_s)

    return TicketWizard([AboutYouAndRequestTypeForm, MailRequestForm], initial=initial)(request)

template_map = dict (bug = "reporter/templates/issue.txt", mailreq = "reporter/templates/mailreq.txt")

def create(ticket_type, project, reporter, email, **kw):
    location = kw.get('location', '')
    if ticket_type == "mailreq":
        project = "networks"
        summary = "Mail address request"
        template = Template(filename=template_map[ticket_type])
        ticket_description = template.render(req_dict=kw, mailreqmapping = mailreqmapping, mailreq_choices = mailreq_choices)
    else:
        desc_d = dict (
            project = project,
            location = location,
            url = kw.get('url',''),
            browser = kw.get('browser', ''),
            os = kw.get('os', ''),
            description = kw.get('description', ''),
            suggestion = kw.get('suggestion', ''),
            )
        template = Template(filename=template_map[ticket_type])
        ticket_description = template.render(**desc_d)
        summary = kw['summary']
    for key in ('summary', 'location'):
        if key in kw: del kw[key]
    return submit(project, reporter, email, summary, ticket_description, location, component="", **kw)

def submit(project, reporter, email, summary, ticket_description="", location=None, component="", **kw):
    #project = "test"
    baseurl_exposed = "https://trac.the-hub.net"
    baseurl = "http://172.24.0.206:13000"
    loginurl = "%s/%s/login" % (baseurl, project)
    newticketurl = "%s/%s/newticket" % (baseurl, project)
    b = mechanize.Browser()
    b.set_handle_robots(False)
    b.open(loginurl)
    forms = list(b.forms())
    for form in forms:
        if set(["user", "password"]).issubset(set([c.name for c in form.controls])):
            nr = forms.index(form)
            b.select_form(nr=nr)
            break
    # else: no form ?
    b['user'] = settings.TRAC_USER
    b['password'] = settings.TRAC_SECRET
    try:
        b.submit()
    except Exception, err:
        if isinstance(err, mechanize._response.seek_wrapper):
            if err.wrapped.code == 501 and 'https_proxy' in os.environ:
                raise Exception("Hint: try unset https_proxy before you start the issue reporter deamon")
        # at this point we should email the request to us
        raise 

    b.open(newticketurl)
    forms = list(b.forms())
    for form in forms:
        if set(["field_reporter", "field_summary"]).issubset(set([c.name for c in form.controls])):
            nr = forms.index(form)
            b.select_form(nr=nr)
            break
    # else: no form ?
    b["field_reporter"] = "%(reporter)s <%(email)s>" % locals()
    b["field_summary"] = summary
    b["field_description"] = ticket_description
    #b["field_type"] = ["defect"]
    b["field_priority"] = ["major"]
    if component:
        b["field_component"] = [component]
    if location and project in ('networks', 'test') and location.lower() != 'other':
        b['field_hub_location'] = [location]
    if 'cc_email' in kw:
        b['field_cc'] = kw['cc_email']
    b.submit('submit')
    links = b.links()
    try:
        defect_url = [lnk for lnk in b.links() if lnk.text == 'View'][0].absolute_url
    except IndexError:
        defect_url = b.geturl()
    return defect_url.replace(baseurl, baseurl_exposed)


